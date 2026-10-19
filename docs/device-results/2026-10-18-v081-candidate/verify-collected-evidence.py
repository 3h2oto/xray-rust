import collections,hashlib,json,pathlib,statistics,subprocess
r=pathlib.Path(__file__).resolve().parent
load=lambda p:json.loads((r/p).read_text())
plan=load('plan.json');expected=plan['coreCommit']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r.parents[1],text=True).strip()==expected
assert not subprocess.check_output(['git','status','--porcelain'],cwd=r.parents[1],text=True).strip()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocols=load('performance-protocols/manifest.json')
assert protocols['status']=='pass' and len(protocols['runs'])==210
assert protocols['candidate']['revision']==expected and protocols['candidate']['tree']==plan['coreTree']
assert all(x['returncode']==0 and not x['surviving_process_group'] and not x['ambient_cpu']['compiler_load_detected'] for x in protocols['runs'])
assert sha(r/'host-cargo/release/xray-rust')==protocols['binarySha256']['candidate']
assert sha(r/'baseline-cargo/release/xray-rust')==protocols['binarySha256']['baseline']
comparisons=load('performance-protocols/protocol-comparisons.json')
assert comparisons['complete'] and len(comparisons['schema4Measurements'])==9
for x in comparisons['schema4Measurements']:
 assert len(x['samples'])==5
 v=statistics.median(x['samples'])
 assert v>=x['threshold'] if x['comparison']=='at-least' else v<=x['threshold']
feature=load('performance-features/performance.json');assert feature['result']=='pass' and len(feature['measurements'])==4
assert all(len(x['samples'])==5 for x in feature['measurements'])
assert load('host-legacy-status.json')['status']=='pass'
ci=load('ci-status.json');assert len(ci['runs'])==3 and all(x['conclusion']=='success' for x in ci['runs'])
for group in ['startup','protocols','ciphers','shared-corrected','legacy','v07','lifecycle','resources','projection-file-descriptor','projection-packet-pump','fakedns-v2-positive','fakedns-v2-recovery']:
 rows=load('ios-'+group+'-result.json');assert rows[-1]['result']=='passed',group
negative=load('ios-fakedns-v2-negative-result.json');assert negative[-1]['result']=='failed' and sum(x['event']=='tcp' for x in negative)==2 and any(x['event']=='dns-fakeip-anchor' for x in negative)
for group,count in [('android',14),('android-shared',6),('android-legacy',8),('android-v07',4)]:
 rows=[json.loads(l) for l in (r/group/'events.jsonl').read_text().splitlines()]
 assert sum(x['kind']=='case-pass' for x in rows)==count and any(x['kind']=='matrix-pass' for x in rows)
 assert not any(x['kind']=='case-fail' for x in rows)
 if group=='android':assert sum(x['kind']=='resource-case-complete' for x in rows)==12
 if group=='android-shared':
  assert sum(x['kind']=='host-adapter-projection' and x['passed'] for x in rows)==6
  assert sum(x['kind']=='ip-asis-negative-control' and x['passed'] for x in rows)==2
rows=[json.loads(l) for l in (r/'android-cancellation/events.jsonl').read_text().splitlines()]
local=[x for x in rows if x['kind']=='local-active-cancellation'];assert len(local)==12 and all(x['localCancellationPassed'] for x in local)
assert sum(x['kind']=='udp-case-pass' for x in rows)==6
assert not any(x['kind']=='udp-case-fail' for x in rows)
followup=load('performance-ss2022-latency-followup/summary.json');assert len(followup['samples'])==15
wan=load('ios-wan-manual/summary.json');assert wan['candidate']==expected and wan['pmtuAuditBeforeAndAfterPassed']
assert [x['result'] for x in wan['results']]==['passed','passed','failed','passed']
assert load('ios-wan-manual/cleanup.json')['temporaryDirectoryRemoved']
report={'candidate':expected,'result':'collected evidence integrity verified; release qualification incomplete','ciRunsPassed':3,'androidFunctionalCasesPassed':32,'androidResourceCasesPassed':12,'androidLocalTCPCancellationPassed':12,'androidUDPCancellationCasesPassed':6,'androidRemoteCloseOutsideBound':sum(not x['remoteCloseBoundPassed'] for x in local),'schema4PerformanceMetricsPassed':13,'legacyPerformancePassed':True,'originalFivePercentComparisonPassed':comparisons['fivePercentAllProfilesPassed'],'ss2022LatencyDiagnosticRatio':followup['pairedRatioMedian'],'manualAppleWANAndLock':'completed: Trojan/VMess passed; SS2022 default failed, owned server socket PMTU condition passed','manualAppleWANPassedRuns':3,'ss2022DefaultPolicyFailedRuns':1,'releaseLimitationsUnresolved':['SS2022 WAN default policy','SS2022 remote EOF bound','5% latency non-regression confirmation']}
(r/'verification-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
