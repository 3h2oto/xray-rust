import collections,datetime,json,pathlib,statistics
r=pathlib.Path(__file__).resolve().parent
out={'candidate':json.loads((r/'plan.json').read_text())['coreCommit'],'scope':'partial measured inventory; not release acceptance','apple':{},'android':{}}
for name in ['startup','protocols','ciphers','shared','shared-corrected','legacy','lifecycle','resources','v07','projection-file-descriptor','projection-packet-pump','ip-asis-negative','ip-demand-recovery','fakedns-positive','fakedns-negative','fakedns-recovery','fakedns-v2-positive','fakedns-v2-negative','fakedns-v2-recovery']:
 p=r/('ios-'+name+'-result.json')
 if not p.exists():continue
 a=json.loads(p.read_text())
 out['apple'][name]={'last':a[-1], 'counts':dict(collections.Counter(e['event'] for e in a)), 'failures':[e for e in a if e['event']=='failure']}
 if name=='resources':
  summaries=[]
  for protocol in sorted({e.get('protocol') for e in a if e.get('event')=='sample'}):
   samples=[e for e in a if e.get('event')=='sample' and e.get('protocol')==protocol]
   baseline=next(e for e in samples if e['stage']=='baseline')
   recover=[e for e in samples if e['stage'].startswith('recovery')]
   if not recover:continue
   limits={'rss':8388608,'footprint':8388608,'threads':8}
   growth={k:max(0,max(e[k] for e in recover)-baseline[k]) for k in limits}
   summaries.append({'protocol':protocol,'baseline':baseline,'growth':growth,'limits':limits,'withinBounds':all(growth[k]<=v for k,v in limits.items()),'recoverySamples':len(recover),'complete':any(e['event']=='resource-complete' and e.get('protocol')==protocol for e in a)})
  out['apple'][name]['bounds']=summaries
for name in ['android','android-shared','android-legacy','android-v07','android-cancellation','android-projection']:
 p=r/name/'events.jsonl'
 if not p.exists():continue
 a=[json.loads(x) for x in p.read_text().splitlines()]
 out['android'][name]={'counts':dict(collections.Counter(e['kind'] for e in a)), 'failures':[e for e in a if 'fail' in e['kind']], 'resourceCases':[e for e in a if e['kind']=='resource-case-complete']}
 if name=='android-cancellation':
  out['android'][name]['localCancellation']=[e for e in a if e['kind']=='local-active-cancellation']
  out['android'][name]['remoteCloseBoundFailures']=[{'case':e['case'],'backend':e['backend'],'mode':e['mode'],'closeReason':e['closed']['reason'],'remoteCloseAfterRequestSeconds':e['closed']['time']-e['closeRequestTime']} for e in a if e['kind']=='local-active-cancellation' and not e['remoteCloseBoundPassed']]
 if name=='android':
  bursts=[e for e in a if e['kind']=='resource-burst' and e.get('completion')]
  out['android'][name]['stressTotals']={k:sum(e['completion'][k] for e in bursts) for k in ['httpPassed','httpFailed','udpPassed','udpFailed']}
  out['android'][name]['resourceRecovery']=[e for e in a if e['kind']=='resource-recovery']
positive=json.loads((r/'ios-fakedns-v2-positive-result.json').read_text())
negative=json.loads((r/'ios-fakedns-v2-negative-result.json').read_text())
recovery=json.loads((r/'ios-fakedns-v2-recovery-result.json').read_text())
out['apple']['ipOnDemandControlEvaluation']={
 'positivePassed':positive[-1].get('result')=='passed',
 'negativeRawResult':negative[-1].get('result'),
 'negativeLiteralTCPPassed':sum(e['event']=='tcp' for e in negative),
 'negativeFakeDNSProofs':sum(e['event']=='dns-fakeip-anchor' for e in negative),
 'negativeDomainWasAttempted':any(e['event']=='tcp-start' and str(e.get('host','')).endswith('.test') for e in negative),
 'negativeExpectedFailureObserved':negative[-1].get('result')=='failed' and sum(e['event']=='tcp' for e in negative)==2 and any(e['event']=='dns-fakeip-anchor' for e in negative),
 'recoveryPassed':recovery[-1].get('result')=='passed',
 'supersededAttempts':'Initial OS-resolved domain control was insufficient. First FakeDNS attempt exposed missing synthetic-domain server allow-route. All original results retained.'}
(r/'device-inventory.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'apple':{k:{'lastEvent':v['last'].get('event'),'status':v['last'].get('result'),'failures':len(v['failures'])} for k,v in out['apple'].items() if 'last' in v},'android':{k:{'casesPassed':v['counts'].get('case-pass',0),'failures':len(v['failures']),'stress':v.get('stressTotals'),'resourceCases':len(v['resourceCases'])} for k,v in out['android'].items()}},indent=2))
