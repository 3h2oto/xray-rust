import base64, hashlib, importlib.util, json, os, pathlib, shlex, subprocess, sys, time
R=pathlib.Path(__file__).resolve().parent
OUT=R/'ios-wan-manual'; OUT.mkdir(exist_ok=True)
sp=importlib.util.spec_from_file_location('remote',R/'remote.py'); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
REMOTE='/tmp/xray-release-081-manual-5b61eee'
PIN='dad34bede2e76f66f3ade83cd1eba71c39bb2a065011528e5571c0638a5f64e1'
SERVICES=['xray-apple-device-probe-server.service','xray-xhttp-device-test.service']
def remote(code): return m.run('python3 -c '+shlex.quote(code))
def upload(source,name):
    p=subprocess.run(['scp','-q','-o','StrictHostKeyChecking=yes','-o','PreferredAuthentications=password','-o','NumberOfPasswordPrompts=1',str(source),m.values['VPS_LOGIN']+'@'+m.values['VPS_HOST']+':'+REMOTE+'/'+name],env={**os.environ,'SSH_ASKPASS':str(R/'ssh-askpass.py'),'SSH_ASKPASS_REQUIRE':'force','DISPLAY':':0'},capture_output=True,text=True,timeout=90)
    if p.returncode: raise RuntimeError('fixture upload failed')
action=sys.argv[1]
if action=='bootstrap':
    assert hashlib.sha256((R/'xray-reference-linux-pinned').read_bytes()).hexdigest()==PIN
    result=remote(f"import pathlib,subprocess,json; p=pathlib.Path({REMOTE!r}); p.mkdir(mode=0o700,exist_ok=False); print(json.dumps({{s:subprocess.check_output(['systemctl','show',s,'--property=ActiveState,MainPID,SubState'],text=True) for s in {SERVICES!r}}}))")
    before=json.loads(result.stdout); assert all('ActiveState=active' in v for v in before.values())
    (OUT/'services-before.json').write_text(json.dumps(before,indent=2))
    upload(R/'xray-reference-linux-pinned','xray')
    upload(R.parents[1]/'scripts/run-v07-apple-protocol-fixture.py','fixture.py')
    upload(R.parents[1]/'scripts/set-xray-ss2022-udp-pmtu.py','pmtu.py')
    remote(f"import pathlib,hashlib;p=pathlib.Path({REMOTE!r})/'xray';assert hashlib.sha256(p.read_bytes()).hexdigest()=={PIN!r};p.chmod(0o700)")
    print('Pinned WAN fixture uploaded; original test services recorded.',flush=True)
elif action=='start':
    protocol=sys.argv[2]; assert protocol in ['trojan','vmess','shadowsocks2022']
    name=protocol+(('-'+sys.argv[3]) if len(sys.argv)>3 else '')
    unit='xray-release-081-manual-'+name+'.service'
    path=REMOTE+'/'+name
    argv=['systemd-run','--unit='+unit,'--property=Type=exec','--property=RuntimeMaxSec=900','--property=TimeoutStopSec=15','--property=ExecStartPre=/usr/bin/systemctl stop '+' '.join(SERVICES),'--property=ExecStopPost=/usr/bin/systemctl start '+' '.join(SERVICES),'python3',REMOTE+'/fixture.py','--bind',m.values['VPS_HOST'],'--reference-binary',REMOTE+'/xray','--reference-sha256',PIN,'--output',path,'--seconds','840','--protocol',protocol,'--port','53053','--mode','transitions']
    code=f'''import subprocess,time,pathlib,json
p=subprocess.run({argv!r},text=True,capture_output=True);assert p.returncode==0,p.stderr
path=pathlib.Path({path!r})/'v07-probe.json'
for _ in range(40):
    if path.exists():break
    time.sleep(0.5)
assert path.exists(),subprocess.check_output(['journalctl','-u',{unit!r},'-n','20','--no-pager'],text=True)
time.sleep(1)
assert subprocess.check_output(['systemctl','is-active',{unit!r}],text=True).strip()=='active'
print(path.read_text())
'''
    result=remote(code); value=json.loads(result.stdout)
    (OUT/(name+'-input.json')).write_text(json.dumps(value,indent=2))
    manifest={'protocol':protocol,'unit':unit,'remotePath':path,'start':time.time(),'port':53053,'referenceSha256':PIN,'referenceCommit':'5ca6f4b7d4dc20a881d4330e498892697627ec0c','candidate':'5b61eee201fac8639cb1dac0349e34af65db90f7','automaticRestoration':SERVICES,'fixtureSeconds':840,'unitRuntimeMaxSeconds':900,'mode':'transitions'}
    (OUT/(name+'-plan.json')).write_text(json.dumps(manifest,indent=2))
    print(name+' WAN fixture ready; bounded lifetime and automatic restoration enabled.',flush=True)
elif action in ['stop','pmtu','pmtu-check']:
    name=sys.argv[2]; plan=json.loads((OUT/(name+'-plan.json')).read_text())
    if action=='stop':
        result=remote(f"import subprocess,json; subprocess.run(['systemctl','stop',{plan['unit']!r}],check=True); print(json.dumps({{s:subprocess.check_output(['systemctl','show',s,'--property=ActiveState,MainPID,SubState'],text=True) for s in {SERVICES!r}}}))")
        (OUT/(name+'-services-restored.json')).write_text(result.stdout)
        assert all('ActiveState=active' in v for v in json.loads(result.stdout).values())
        print(name+' stopped; both original test services restored.')
    else:
        argv=['python3',REMOTE+'/pmtu.py','--unit',plan['unit'],'--config',plan['remotePath']+'/server.json','--executable',REMOTE+'/xray','--sha256',PIN,'--port','53053']
        if action=='pmtu-check':argv.append('--check')
        result=m.run(shlex.join(argv));(OUT/(name+'-'+action+'.json')).write_text(result.stdout);print('Verified and recorded per-fixture SS2022 UDP socket PMTU setting: '+action)
elif action=='launch':
    name=sys.argv[2]; device='<apple-device>'; bundle='org.texforge.XrayClient'
    def dc(args):
        p=subprocess.run(['xcrun','devicectl','device',*args[:2],'--device',device,'--timeout','30',*args[2:]],capture_output=True,text=True,timeout=45)
        if p.returncode: raise RuntimeError(p.stdout+p.stderr)
    dc(['copy','to','--source',str(OUT/(name+'-input.json')),'--destination','Documents/v07-probe.json','--domain-type','appDataContainer','--domain-identifier',bundle])
    after=time.time();dc(['process','launch','--terminate-existing','--environment-variables','{"XRAY_V07_DEVICE_PROBE":"1"}','--json-output',str(OUT/(name+'-launch.json')),bundle])
    (OUT/'active.json').write_text(json.dumps({'name':name,'after':after}));print('Started iPhone '+name+' transitions probe.')
elif action=='collect':
    active=json.loads((OUT/'active.json').read_text());name=active['name']; dest=OUT/(name+'-result.json')
    p=subprocess.run(['xcrun','devicectl','device','copy','from','--device','<apple-device>','--timeout','30','--source','Documents/v07-result.json','--destination',str(dest),'--domain-type','appDataContainer','--domain-identifier','org.texforge.XrayClient'],capture_output=True,text=True,timeout=45)
    if p.returncode: raise RuntimeError(p.stdout+p.stderr)
    rows=json.loads(dest.read_text()); important=[v for v in rows if v.get('event') in ['action-required','transition-recovered','transition-failed','lock-interval','failure','complete','recovery-retry','carrier','carrier-route','locked','unlocked']]
    print(json.dumps({'name':name,'events':len(rows),'important':important[-12:],'last':rows[-1]},ensure_ascii=False,indent=2))
