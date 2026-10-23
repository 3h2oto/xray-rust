//! Client-side handshakes that open a tunnel through an upstream proxy.

mod socks;

pub use socks::{
    decode_socks5_udp_reply, encode_socks5_udp_request, socks5_connect, socks5_udp_associate,
    validate_connect_target, SocksClientError, SocksUdpDrop, MAX_SOCKS_UDP_DATAGRAM_LENGTH,
};
