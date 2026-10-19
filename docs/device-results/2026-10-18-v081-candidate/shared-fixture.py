#!/usr/bin/env python3
import argparse,atexit,copy,importlib.util,json,os,pathlib,select,socket,subprocess,sys,uuid
from urllib.parse import urlencode
ROOT=pathlib.Path(__file__).resolve().parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=argparse.ArgumentParser(add_help=False);p.add_argument('--platform',choices=['apple','android'],required=True)
a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
if a.platform=='android':
    android=module('shared_android',ROOT/'scripts/run-v08-android-protocol-fixture.py')
    f=android.fixture;f.Echo=android.Oracle;f.tcp_echo=android.http_probe
else:
    f=module('shared_apple',ROOT/'scripts/run-v07-apple-protocol-fixture.py')
original=f.write_fixtures
children=[]
def cleanup():
    for child,log in children:
        if child.poll() is None:
            child.terminate()
            try:child.wait(5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        log.close()
atexit.register(cleanup)
def port(bind):
    with socket.socket() as s:s.bind((bind,0));return s.getsockname()[1]
def write(root,bind,tcp_port,udp_port,dns_port,**kwargs):
    original(root,bind,tcp_port,udp_port,dns_port,**{**kwargs,'protocol':'trojan','port':None})
    server=json.loads((root/'server.json').read_text());env=json.loads((root/'v07-probe.json').read_text())
    common=json.loads(env['cases'][0]['configJSON']);server['inbounds']=[];env['cases']=[]
    keys=json.loads(subprocess.check_output([str(ROOT/'target/release-081/vless-keys'),'keypair','x25519']))
    for name in ('vless-encryption','ip-on-demand','xhttp-download-session'):
        user=str(uuid.uuid4());carrier=port(bind);stream={'network':'raw'};server_stream={'network':'raw'}
        encryption='none';decryption='none';listen=bind
        if name in ('vless-encryption','ip-on-demand'):
            encryption='mlkem768x25519plus.random.0rtt.'+keys['public']
            decryption='mlkem768x25519plus.random.600s.'+keys['private']
        if name=='xhttp-download-session':
            listen='127.0.0.1';carrier=port(listen)
            server_stream={'network':'xhttp','xhttpSettings':{'path':'/split/','mode':'auto'}}
            log=(root/'download-bridge.log').open('w')
            child=subprocess.Popen([str(ROOT/'target/release-081/download-bridge'),'bridge',f'127.0.0.1:{carrier}'],stdout=subprocess.PIPE,stderr=log,text=True,env={**os.environ,'XRAY_FIXTURE_BIND':bind})
            children.append((child,log))
            if not select.select([child.stdout],[],[],20)[0]:raise RuntimeError('bridge startup timeout')
            bridge=json.loads(child.stdout.readline());client_port=int(bridge['tcp'].rsplit(':',1)[1])
            def transport(download):
                return {'network':'xhttp','security':'tls','tlsSettings':{'serverName':'download-oracle.test','alpn':['h2' if download else 'http/1.1'],'pinnedPeerCertSha256':bridge['pin']},'xhttpSettings':{'path':'/download/' if download else '/upload/','mode':'packet-up','xmux':{'maxConnections':1},'scMinPostsIntervalMs':1}}
            stream=transport(False);down=transport(True);down.update(address=bind,port=client_port)
            stream['xhttpSettings']['downloadSettings']=down
        else:client_port=carrier
        server['inbounds'].append({'listen':listen,'port':carrier,'protocol':'vless','settings':{'clients':[{'id':user}],'decryption':decryption},'streamSettings':server_stream})
        config=copy.deepcopy(common)
        outbound={'tag':'proxy','protocol':'vless','settings':{'vnext':[{'address':bind,'port':client_port,'users':[{'id':user,'encryption':encryption}]}]},'streamSettings':stream}
        config['outbounds']=[outbound]
        if name=='ip-on-demand':
            config['dns'].update(queryStrategy='UseIPv4',fakeIp={'enabled':True,'ipv4Pool':'198.19.0.0/16','poolSize':32768,'ttl':60})
            config['outbounds'].insert(0,{'tag':'blocked','protocol':'blackhole'})
            config['routing']={'domainStrategy':'IPOnDemand','rules':[{'type':'field','ip':['198.51.100.0/24','2001:db8::/32'],'outboundTag':'proxy'}]}
        query={'encryption':encryption,'type':'tcp'}
        if name=='xhttp-download-session':query.update(type='xhttp',security='tls',sni='download-oracle.test',path='/upload/',mode='packet-up')
        env['cases'].append({'format':'vless','label':name,'caseId':name,'expectFakeDNS':name=='ip-on-demand','text':f'vless://{user}@{bind}:{client_port}?{urlencode(query)}','serverAddress':bind,'configJSON':json.dumps(config)})
    server['routing']['rules'].insert(0,{'type':'field','domain':['full:'+env['probeHost']],'outboundTag':'echo'})
    (root/'server.json').write_text(json.dumps(server,indent=2)+'\n');(root/'v07-probe.json').write_text(json.dumps(env,indent=2)+'\n')
f.write_fixtures=write
f.main()
