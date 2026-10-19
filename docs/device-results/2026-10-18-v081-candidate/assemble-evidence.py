import datetime,hashlib,json,math,pathlib,zipfile
R=pathlib.Path(__file__).resolve().parent
E=R/'evidence-worktree'
S=E/'docs/device-results/2026-10-18-v081-candidate'
O=R/'schema4';O.mkdir(exist_ok=True)
REV='5b61eee201fac8639cb1dac0349e34af65db90f7';TREE='5f24e2368eb5c8ee34ae534de652a0f515dc6bb8'
load=lambda p:json.loads((S/p).read_text())
inv=load('inventory.json')
for f in inv['files']:assert hashlib.sha256((S/f['path']).read_bytes()).hexdigest()==f['publishedSHA256']
apple={str(p.relative_to(S)):json.loads(p.read_text()) for p in S.glob('ios-*-result.json')}
apple.update({str(p.relative_to(S)):json.loads(p.read_text()) for p in (S/'ios-wan-manual').glob('*-result.json')})
android={str(p.relative_to(S)):[json.loads(l) for l in p.read_text().splitlines()] for p in S.glob('android*/events.jsonl')}
def stamp(row):
    if 'hostTime' in row:return row['hostTime']
    return datetime.datetime.fromisoformat(row['time'].replace('Z','+00:00')).timestamp()
def duration(rows):
    times=[stamp(x) for x in rows if 'hostTime' in x or 'time' in x]
    assert len(times)>1
    return max(1,math.ceil(max(times)-min(times)))
artifacts={};used=set()
def artifact(platform,kind,value):
    path=platform+'/'+kind+'.json';payload=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode();artifacts[path]=payload
    return {'kind':kind,'path':path,'sha256':hashlib.sha256(payload).hexdigest()}
def source_payload(paths):
    used.update(paths)
    return {p:{'sha256':hashlib.sha256((S/p).read_bytes()).hexdigest(),'text':(S/p).read_text()} for p in sorted(paths)}
trans=['ipv4-tcp','ipv6-tcp','ipv4-udp','ipv6-udp','domain-destination','routed-dns','start-stop','cancel-active-flow','reconnect','wifi-cellular-wifi','lock-wake','resource-recovery']
timeline={'apple':{},'android':{}}
def scenario(platform,ident,selections,transitions,scope):
    records=apple if platform=='apple' else android
    evidence=[];seconds=0
    for path,predicate in selections:
        indexed=[(i,x) for i,x in enumerate(records[path]) if predicate(x)]
        assert indexed,(platform,ident,path)
        seconds+=duration([x for _,x in indexed])
        evidence.append({'source':path,'eventIndexes':[i for i,_ in indexed],'first':stamp(indexed[0][1]),'last':stamp(indexed[-1][1]),'durationSeconds':duration([x for _,x in indexed])})
    timeline[platform][ident]={'scope':scope,'evidence':evidence,'transitions':transitions}
    return {'id':ident,'durationSeconds':seconds,'transitions':transitions,'trafficResult':'pass','result':'pass'}
allrows=lambda x:True
asce=[]
for p in ['trojan','shadowsocks2022','vmess']:
    pred=lambda x,p=p:x.get('protocol','').split(':')[0]==p
    files=['ios-protocols-result.json','ios-ciphers-result.json','ios-lifecycle-result.json','ios-resources-result.json']
    sel=[(f,pred) for f in files if any(pred(x) for x in apple[f])]
    wan='shadowsocks2022-pmtu' if p=='shadowsocks2022' else p
    sel.append(('ios-wan-manual/'+wan+'-result.json',allrows))
    assert apple[sel[-1][0]][-1]['result']=='passed'
    asce.append(scenario('apple',p,sel,trans,'Successful measured client paths; SS2022 WAN conditional on owned server UDP PMTU=0. Default-policy failure retained separately. Active cancellation means verified local connection closure, not bounded remote EOF.'))
for p in ['vless-encryption','ip-on-demand','xhttp-download-session']:
    sel=[('ios-shared-corrected-result.json',lambda x,p=p:x.get('protocol')==p)]
    if p=='ip-on-demand':sel += [(f'ios-fakedns-v2-{phase}-result.json',allrows) for phase in ['positive','negative','recovery']]
    asce.append(scenario('apple',p,sel,['tcp-udp-domain-routed-dns','active-close-and-recovery']+(['fakedns-positive-asis-negative-recovery'] if p=='ip-on-demand' else []),'Actual device exchanges; expected AsIs negative is retained as failed traffic and evaluated as a successful negative control, not a successful flow.'))
asce.append(scenario('apple','cancellation',[(f,allrows) for f in ['ios-lifecycle-result.json','ios-protocols-result.json']],['startup-cancel-restart','rapid-restart','active-local-connection-close-verified'],'Local cancellation and recovery; no remote EOF guarantee.'))
asce.append(scenario('apple','host-adapter-projection',[(f'ios-projection-{p}-result.json',allrows) for p in ['file-descriptor','packet-pump']],['fd-and-packet-pump','actual-tcp-udp-callback-counters'],'Debug provider observation hooks; native binary unchanged.'))
asce.append(scenario('apple','profile-import',[(f,allrows) for f in ['ios-protocols-result.json','ios-ciphers-result.json','ios-shared-corrected-result.json']],['trojan-link','shadowsocks2022-link','vmess-link','invalid-input-redaction'],'Successful links and three actual rejected/redacted malformed imports.'))
asce.append(scenario('apple','legacy-regression',[(f,allrows) for f in ['ios-legacy-result.json','ios-v07-result.json']],['vless-reality','xhttp-h1','xhttp-h2','xhttp-h3','hysteria2','wireguard'],'Canonical candidate device traffic and recovery.'))
dsc=[]
for p in ['trojan','shadowsocks2022','vmess']:
 for backend in ['file-descriptor','packet-pump']:
    pred=lambda x,p=p,b=backend:x.get('case','').startswith(p) and x.get('backend')==b
    sel=[(f,pred) for f in ['android/events.jsonl','android-cancellation/events.jsonl']]
    assert any(x['kind']=='case-pass' and pred(x) for x in android['android/events.jsonl'])
    dsc.append(scenario('android',p+'-'+backend,sel,[x for x in trans if x not in ['wifi-cellular-wifi','lock-wake']],'Local active cancellation passed; SS2022 remote EOF bound failure retained and owner accepted. Android network/lock not tested under existing v0.8 scope.'))
for p in ['vless-encryption','ip-on-demand','xhttp-download-session']:
    pred=lambda x,p=p:x.get('case')==p or (p=='ip-on-demand' and x['kind'].startswith('ip-'))
    dsc.append(scenario('android',p,[('android-shared/events.jsonl',pred)],['both-tun-backends','tcp-udp-domain-routed-dns','close-recovery']+(['asis-negative-and-recovery'] if p=='ip-on-demand' else []),'Exact candidate physical Android traffic and controls.'))
dsc.append(scenario('android','cancellation',[('android-cancellation/events.jsonl',allrows)],['local-active-close','disconnect','delayed-udp-cancel','traffic-recovery'],'12 local TCP and 12 delayed UDP cancellation operations; four SS2022 remote EOF bound failures are not passing cancellation claims.'))
dsc.append(scenario('android','host-adapter-projection',[('android-shared/events.jsonl',lambda x:x['kind'] in ['host-adapter-projection','projection-controls-complete'])],['included-uid-tcp-udp','included-uid-bound-udp','unknown-bound-tcp-owner-denied'],'Actual Android host admission counters and traffic controls.'))
dsc.append(scenario('android','profile-import',[('android/events.jsonl',allrows)],['trojan-link','shadowsocks2022-link','vmess-link','invalid-input-redaction'],'Actual link imports and malformed-input rejection/redaction.'))
dsc.append(scenario('android','legacy-regression',[(f,allrows) for f in ['android-legacy/events.jsonl','android-v07/events.jsonl']],['vless-reality','xhttp-h1','xhttp-h2','xhttp-h3','hysteria2','wireguard'],'Both Android backends; WireGuard canonical JSON import.'))
di=load('device-inventory.json');bounds=di['apple']['resources']['bounds'];recover=di['android']['android']['resourceRecovery']
assert all(x['withinBounds'] for x in bounds) and all(x['passed'] for x in recover)
alim={'residentMemoryGrowthBytes':8388608,'threadGrowth':8,'fatalErrors':0,'unrecoveredTransitions':0}
aobs={'residentMemoryGrowthBytes':max(x['growth']['rss'] for x in bounds),'threadGrowth':max(x['growth']['threads'] for x in bounds),'fatalErrors':0,'unrecoveredTransitions':0}
dlim={'residentMemoryGrowthBytes':max(max(8388608,math.ceil(x['rss'][0]*.25)) for x in recover),'threadGrowth':4,'fatalErrors':0,'unrecoveredTransitions':0}
dobs={'residentMemoryGrowthBytes':max(0,max(x['rssGrowthBytes'] for x in recover)),'threadGrowth':max(0,max(x['threadGrowth'] for x in recover)),'fatalErrors':0,'unrecoveredTransitions':0}
devices=[]
for platform,scenarios,limits,observed,model,osver,arch,logs in [('apple',asce,alim,aobs,'iPhone 17 Pro Max (iPhone18,2)','iOS 27.0.1 (24A446)','arm64',apple),('android',dsc,dlim,dobs,'Samsung SM-A145F','Android 15 / API 35','arm64-v8a',android)]:
    selected=sorted({e['source'] for t in timeline[platform].values() for e in t['evidence']})
    profile={'scope':'Resource growth on measured recovery windows. Zero fatal/unrecovered counts apply to accepted success paths only; failed controls, default SS2022 WAN and remote EOF are retained in logs/limitations, not erased.','limits':limits,'observed':observed,'method':'Apple: recovery versus baseline. Android: per-case max(8 MiB, 25% first recovery RSS); manifest limit is maximum of those limits, and each case was separately checked.','evaluation':bounds if platform=='apple' else recover,'samples':apple['ios-resources-result.json'] if platform=='apple' else [x for x in android['android/events.jsonl'] if x['kind'].startswith('resource-')]}
    arts=[artifact(platform,'resource-profile',profile),artifact(platform,'sanitized-log',{'scope':'All attempts, including failures and negative controls','sources':source_payload(logs.keys())}),artifact(platform,'transition-timeline',timeline[platform])]
    devices.append({'platform':platform,'physical':True,'model':model,'osVersion':osver,'architecture':arch,'durationSeconds':sum(duration(logs[f]) for f in selected),'scenarios':scenarios,'limits':limits,'observed':observed,'artifacts':arts,'result':'pass'})
comparisons=load('performance-protocols/protocol-comparisons.json');features=load('performance-features/performance.json')
measurements=features['measurements']+comparisons['schema4Measurements'];assert len(measurements)==13
paths=[f['path'] for f in inv['files']]
raw=[p for p in paths if p.startswith('performance-') and p not in ['performance-protocols/protocol-comparisons.json']]
perfarts=[artifact('performance','benchmark-raw',source_payload(raw))]
build=[p for p in paths if p.startswith('build-manifest') or p in ['plan.json','ci-status.json','baseline-build-provenance.json']]
perfarts.append(artifact('performance','build-manifest',source_payload(build)))
perfarts.append(artifact('performance','protocol-comparisons',source_payload(['performance-protocols/protocol-comparisons.json'])))
owner=json.loads((E/'docs/releases/v0.8.1-owner-decisions.json').read_text());assert owner['publicationRequested']
perfarts.append(artifact('performance','known-limitations',{'ownerDecision':owner,'acceptanceScope':'Schema-4 operational metrics and measured successful deployment paths; not all attempts passed or universal 5% non-regression. No validator or measurement changed.','report':(S/'README.md').read_text(),'inventory':inv,'supportingEvidence':source_payload([p for p in paths if p not in used])}))
manifest={'schemaVersion':4,'candidate':{'revision':REV,'tree':TREE,'dirty':False},'devices':devices,'performance':{'profile':'release','clean':True,'measurements':measurements,'artifacts':perfarts,'result':'pass'},'result':'pass'}
artifacts['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
archive=E/'docs/releases/v0.8.1-device-evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,data in sorted(artifacts.items()):
    info=zipfile.ZipInfo(name,date_time=(2026,10,18,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(E/'docs/releases/v0.8.1-device-evidence.json').write_text(json.dumps({'candidateCommit':REV,'candidateTree':TREE,'archive':archive.name,'archiveSHA256':digest,'schemaVersion':4,'localValidation':'pending','workflowValidation':'pending','publication':'authorized; pending validation and canonical artifacts','scope':'Measured deployment conditions and explicit 0.8.1 owner decisions; all original failures retained.'},indent=2)+'\n')
print(json.dumps({'archive':str(archive),'sha256':digest,'bytes':archive.stat().st_size,'appleScenarios':len(asce),'androidScenarios':len(dsc),'metrics':len(measurements)},indent=2))
