//! `socks` outbound through xray-rust's own password-protected SOCKS inbound.
//!
//! One core runs both hops: `client-in` routes everything to the `socks`
//! outbound, which dials `upstream-in` on a fixed loopback port; `upstream-in`
//! authenticates with RFC 1929 and forwards to Freedom. UDP edge cases use a
//! scripted upstream instead of `upstream-in`, so the test controls the relay.

use super::*;
use xray_proxy::inbound::SocksUdpDatagram;

const UPSTREAM_INBOUND: &str = r#",
    {"tag": "upstream-in", "protocol": "socks", "listen": "127.0.0.1", "port": UPSTREAM_PORT,
     "settings": {"auth": "password", "udp": true,
        "accounts": [{"user": "synthetic-user", "pass": "synthetic-pass"}]}}"#;

/// `client-in` → `via-socks` → `127.0.0.1:upstream_port`, optionally served by
/// the core's own `upstream-in`.
fn chain_config(upstream_port: u16, pass: &str, upstream_inbound: bool) -> CoreConfig {
    let upstream = if upstream_inbound {
        UPSTREAM_INBOUND.replace("UPSTREAM_PORT", &upstream_port.to_string())
    } else {
        String::new()
    };
    let raw = format!(
        r#"{{
        "inbounds": [
            {{"tag": "client-in", "protocol": "socks", "listen": "127.0.0.1", "port": 0,
             "settings": {{"auth": "noauth", "udp": true}}}}{upstream}
        ],
        "outbounds": [
            {{"tag": "direct", "protocol": "freedom"}},
            {{"tag": "via-socks", "protocol": "socks",
             "settings": {{"address": "127.0.0.1", "port": {upstream_port},
                "user": "synthetic-user", "pass": "{pass}"}}}}
        ],
        "routing": {{"rules": [
            {{"type": "field", "inboundTag": ["client-in"], "outboundTag": "via-socks"}}
        ]}}
    }}"#
    );
    parse_xray_json(&raw)
        .expect("synthetic SOCKS chain config parses")
        .config
}

fn socks_chain_config(upstream_port: u16, pass: &str) -> CoreConfig {
    chain_config(upstream_port, pass, true)
}

async fn start_socks_chain(pass: &str) -> (Core, SocketAddr) {
    let mut core = Core::new(socks_chain_config(allocate_unused_loopback_port(), pass)).unwrap();
    core.start().await.unwrap();
    let client_in = core.inbound_addr(Some("client-in")).unwrap();
    (core, client_in)
}

/// No-auth SOCKS5 CONNECT to an IPv4 target; returns the reply code.
async fn socks5_connect_ipv4(client: &mut TcpStream, target: SocketAddr) -> u8 {
    let SocketAddr::V4(target) = target else {
        panic!("echo servers bind IPv4 loopback");
    };
    client.write_all(&[5, 1, 0]).await.unwrap();
    let mut method = [0; 2];
    client.read_exact(&mut method).await.unwrap();
    assert_eq!(method, [5, 0]);

    let mut request = vec![5, 1, 0, 1];
    request.extend_from_slice(&target.ip().octets());
    request.extend_from_slice(&target.port().to_be_bytes());
    client.write_all(&request).await.unwrap();
    let mut reply = [0; 10];
    client.read_exact(&mut reply).await.unwrap();
    reply[1]
}

#[tokio::test]
async fn socks_outbound_tunnels_tcp_through_a_password_upstream() {
    timeout(Duration::from_secs(5), async {
        let (echo_addr, echo_handle) = spawn_echo_server().await;
        let (mut core, client_in) = start_socks_chain("synthetic-pass").await;

        let mut client = TcpStream::connect(client_in).await.unwrap();
        assert_eq!(socks5_connect_ipv4(&mut client, echo_addr).await, 0);
        client
            .write_all(b"through the socks outbound")
            .await
            .unwrap();
        let mut echoed = [0; 26];
        client.read_exact(&mut echoed).await.unwrap();
        assert_eq!(&echoed, b"through the socks outbound");

        drop(client);
        core.stop().await.unwrap();
        timeout(Duration::from_secs(1), echo_handle)
            .await
            .unwrap()
            .unwrap();
    })
    .await
    .unwrap();
}

#[tokio::test]
async fn socks_outbound_fails_the_flow_when_the_upstream_rejects_its_password() {
    timeout(Duration::from_secs(5), async {
        let (echo_addr, echo_handle) = spawn_echo_server().await;
        let (mut core, client_in) = start_socks_chain("wrong-pass").await;

        let mut client = TcpStream::connect(client_in).await.unwrap();
        assert_ne!(
            socks5_connect_ipv4(&mut client, echo_addr).await,
            0,
            "a rejected upstream login must not open the tunnel"
        );

        drop(client);
        core.stop().await.unwrap();
        echo_handle.abort();
    })
    .await
    .unwrap();
}

/// A client of `client-in`'s own UDP association.
struct UdpClient {
    _control: TcpStream,
    socket: UdpSocket,
    relay: SocketAddr,
}

impl UdpClient {
    async fn associate(client_in: SocketAddr) -> Self {
        let mut control = TcpStream::connect(client_in).await.unwrap();
        let relay = socks5_udp_associate(&mut control).await;
        let socket = UdpSocket::bind((Ipv4Addr::LOCALHOST, 0)).await.unwrap();
        Self {
            _control: control,
            socket,
            relay,
        }
    }

    async fn send(&self, target: SocketAddr, payload: &[u8]) {
        let target = Target::new(
            RoutingTargetAddr::Ip(target.ip()),
            target.port(),
            RoutingNetwork::Udp,
        );
        let request = encode_socks5_udp_datagram(&target, payload).unwrap();
        self.socket.send_to(&request, self.relay).await.unwrap();
    }

    async fn recv(&self) -> Bytes {
        let mut response = [0; 2048];
        let (len, _) = timeout(Duration::from_secs(2), self.socket.recv_from(&mut response))
            .await
            .expect("a datagram comes back through the chain")
            .unwrap();
        parse_socks5_udp_datagram(&response[..len]).unwrap().payload
    }
}

/// One association accepted by [`scripted_upstream_association`].
struct ScriptedAssociation {
    control: TcpStream,
    /// The client endpoint declared in the UDP ASSOCIATE request.
    declared: SocketAddr,
    relay: UdpSocket,
}

/// Plays a password SOCKS5 server for one UDP ASSOCIATE on `listener`. It
/// replies with an unspecified bound address, so the client must substitute
/// the server address.
async fn scripted_upstream_association(listener: &TcpListener) -> ScriptedAssociation {
    let (mut control, _) = timeout(Duration::from_secs(2), listener.accept())
        .await
        .expect("the outbound opens a control connection")
        .unwrap();
    let mut greeting = [0; 3];
    control.read_exact(&mut greeting).await.unwrap();
    assert_eq!(greeting, [5, 1, 2]);
    control.write_all(&[5, 2]).await.unwrap();
    let mut auth = [0; 2 + 14 + 1 + 14];
    control.read_exact(&mut auth).await.unwrap();
    assert_eq!(auth, *b"\x01\x0esynthetic-user\x0esynthetic-pass");
    control.write_all(&[1, 0]).await.unwrap();

    let mut head = [0; 4];
    control.read_exact(&mut head).await.unwrap();
    assert_eq!(&head[..3], &[5, 3, 0]);
    let declared = match head[3] {
        1 => {
            let mut raw = [0; 6];
            control.read_exact(&mut raw).await.unwrap();
            SocketAddr::from((
                Ipv4Addr::new(raw[0], raw[1], raw[2], raw[3]),
                u16::from_be_bytes([raw[4], raw[5]]),
            ))
        }
        other => panic!("unexpected declared address type {other}"),
    };

    let relay = UdpSocket::bind((Ipv4Addr::LOCALHOST, 0)).await.unwrap();
    let mut reply = vec![5, 0, 0, 1, 0, 0, 0, 0];
    reply.extend_from_slice(&relay.local_addr().unwrap().port().to_be_bytes());
    control.write_all(&reply).await.unwrap();
    ScriptedAssociation {
        control,
        declared,
        relay,
    }
}

impl ScriptedAssociation {
    /// Receives one request datagram and checks that it comes from the
    /// declared endpoint.
    async fn recv(&self) -> (SocketAddr, SocksUdpDatagram) {
        let mut buffer = [0; 2048];
        let (len, source) = timeout(Duration::from_secs(2), self.relay.recv_from(&mut buffer))
            .await
            .expect("the outbound relays the datagram")
            .unwrap();
        assert_ne!(self.declared.port(), 0, "Xray's 0.0.0.0:0 is not declared");
        assert_eq!(source.port(), self.declared.port());
        assert!(self.declared.ip().is_unspecified() || self.declared.ip() == source.ip());
        (source, parse_socks5_udp_datagram(&buffer[..len]).unwrap())
    }
}

const SYNTHETIC_UDP_TARGET: SocketAddr =
    SocketAddr::new(IpAddr::V4(Ipv4Addr::new(192, 0, 2, 10)), 53);

async fn start_scripted_chain() -> (Core, SocketAddr, TcpListener) {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let mut core = Core::new(chain_config(port, "synthetic-pass", false)).unwrap();
    core.start().await.unwrap();
    let client_in = core.inbound_addr(Some("client-in")).unwrap();
    (core, client_in, listener)
}

#[tokio::test]
async fn socks_outbound_relays_udp_through_a_password_upstream() {
    timeout(Duration::from_secs(5), async {
        let (echo_addr, echo_handle) = spawn_udp_echo_server().await;
        let (mut core, client_in) = start_socks_chain("synthetic-pass").await;

        // `upstream-in` refuses an association whose declared port is unset
        // and admits datagrams only from the declared endpoint, so the echo
        // proves the outbound declared its real relay socket.
        let client = UdpClient::associate(client_in).await;
        client.send(echo_addr, b"udp via socks").await;
        assert_eq!(client.recv().await.as_ref(), b"udp via socks");

        drop(client);
        core.stop().await.unwrap();
        timeout(Duration::from_secs(1), echo_handle)
            .await
            .unwrap()
            .unwrap();
    })
    .await
    .unwrap();
}

#[tokio::test]
async fn socks_outbound_drops_bad_relay_datagrams_without_ending_the_session() {
    timeout(Duration::from_secs(10), async {
        let (mut core, client_in, listener) = start_scripted_chain().await;
        let client = UdpClient::associate(client_in).await;

        client.send(SYNTHETIC_UDP_TARGET, b"ping").await;
        let upstream = scripted_upstream_association(&listener).await;
        let (source, request) = upstream.recv().await;
        assert_eq!(request.payload.as_ref(), b"ping");
        assert_eq!(
            request.target,
            Target::new(
                RoutingTargetAddr::Ip(SYNTHETIC_UDP_TARGET.ip()),
                SYNTHETIC_UDP_TARGET.port(),
                RoutingNetwork::Udp,
            )
        );

        let fragmented = [&[0, 0, 1, 1, 192, 0, 2, 10, 0, 53][..], b"fragment"].concat();
        for bad in [
            &[0, 0][..],
            &[0, 0, 0, 9, 1, 2, 3],
            &[0, 0, 0, 3, 0, 0, 53],
            &fragmented,
        ] {
            upstream.relay.send_to(bad, source).await.unwrap();
        }
        let reply = [&[0, 0, 0, 1, 192, 0, 2, 10, 0, 53][..], b"pong"].concat();
        upstream.relay.send_to(&reply, source).await.unwrap();
        assert_eq!(client.recv().await.as_ref(), b"pong");

        // The same association still carries traffic both ways.
        client.send(SYNTHETIC_UDP_TARGET, b"again").await;
        let (_, request) = upstream.recv().await;
        assert_eq!(request.payload.as_ref(), b"again");
        upstream.relay.send_to(&reply, source).await.unwrap();
        assert_eq!(client.recv().await.as_ref(), b"pong");
        assert!(
            timeout(Duration::from_millis(200), listener.accept())
                .await
                .is_err(),
            "dropped datagrams must not end the association"
        );

        drop(client);
        core.stop().await.unwrap();
    })
    .await
    .unwrap();
}

#[tokio::test]
async fn socks_outbound_ends_the_udp_session_when_the_upstream_closes_control() {
    timeout(Duration::from_secs(10), async {
        let (mut core, client_in, listener) = start_scripted_chain().await;
        let client = UdpClient::associate(client_in).await;

        client.send(SYNTHETIC_UDP_TARGET, b"first").await;
        let upstream = scripted_upstream_association(&listener).await;
        let (source, _) = upstream.recv().await;
        let reply = [&[0, 0, 0, 1, 192, 0, 2, 10, 0, 53][..], b"reply"].concat();
        upstream.relay.send_to(&reply, source).await.unwrap();
        assert_eq!(client.recv().await.as_ref(), b"reply");

        // Close only the control connection; the relay socket stays open, so
        // a session that ignored the control connection would keep using it.
        let ScriptedAssociation { control, relay, .. } = upstream;
        drop(control);
        let reopened = async {
            loop {
                client.send(SYNTHETIC_UDP_TARGET, b"next").await;
                if let Ok(accepted) = timeout(Duration::from_millis(50), listener.accept()).await {
                    return accepted.unwrap();
                }
            }
        };
        timeout(Duration::from_secs(3), reopened)
            .await
            .expect("the next datagram opens a new association");

        drop((client, relay));
        core.stop().await.unwrap();
    })
    .await
    .unwrap();
}
