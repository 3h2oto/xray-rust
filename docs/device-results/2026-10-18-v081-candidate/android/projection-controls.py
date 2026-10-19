import copy,json,time
import drive as d
try:
 env=json.loads((d.ROOT/'fixture-v2/v07-probe.json').read_text())
 positive=next(c for c in env['cases'] if c['caseId']=='ip-on-demand')
 negative=copy.deepcopy(positive);config=json.loads(negative['configJSON']);config['routing']['domainStrategy']='AsIs';negative['configJSON']=json.dumps(config)
 for backend in ['file-descriptor','packet-pump']:
  d.emit('ip-asis-negative-plan',backend=backend,expected='domain traffic rejected; literal IP still works')
  d.host_stop();d.install_profile(negative);assert d.host_start(backend)['state']=='running'
  d.emit('ip-asis-literal-control',backend=backend,status=d.traffic(env,'ipv4',1))
  try:
   result=d.traffic(env,'domain',1);d.emit('ip-asis-negative-control',backend=backend,passed=False,unexpectedTraffic=result)
  except RuntimeError:
   state=d.status(d.PROBE);ok=int(state.get('http-failed',0))+int(state.get('udp-failed',0))>0
   d.emit('ip-asis-negative-control',backend=backend,passed=ok,status=state)
  d.host_stop();d.install_profile(positive);assert d.host_start(backend)['state']=='running'
  d.emit('ip-on-demand-recovery-control',backend=backend,status=d.traffic(env,'domain',2));d.host_stop()
 protocols=json.loads((d.ROOT.parent/'android/fixture/v07-probe.json').read_text())
 cases=[c for c in protocols['cases'] if c['caseId'] in ('trojan-tls','shadowsocks2022-2022-blake3-chacha20-poly1305','vmess-auto')]
 for case in cases:
  for backend in ['file-descriptor','packet-pump']:
   d.host_stop();d.install_profile(case);started=time.time()
   d.command(d.HOST,'connect',('--es','tun-backend',backend,'--ez','probe-only','true','--ez','tun-admission','true'))
   state=d.wait_status(d.HOST,lambda s:s.get('state') in ('running','failed','fatal'));assert state['state']=='running',state
   status=d.traffic(protocols,'ipv4',2);d.command(d.HOST,'close-connections')
   raw=d.adb('logcat','-d','-v','epoch','-s','XrayDeviceGate:I','*:S')
   samples=[]
   for line in raw.splitlines():
    if 'XRAY_ANDROID_SAMPLE ' in line and float(line.split()[0])>=started:
     samples.append(json.loads(line.split('XRAY_ANDROID_SAMPLE ',1)[1]))
   sample=samples[-1];passed=sample['admissionEnabled'] and sample['admissionAllowed']>0 and sample['fatalTunErrors']==0
   d.emit('host-adapter-projection',case=case['caseId'],backend=backend,passed=passed,traffic=status,sample=sample)
   assert passed;d.host_stop()
 d.emit('projection-controls-complete')
finally:
 d.probe_stop();d.host_stop();d.log_snapshot('projection-logcat.log')
