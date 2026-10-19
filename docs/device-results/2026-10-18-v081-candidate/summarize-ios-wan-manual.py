import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parent
W=R/'ios-wan-manual'
results=[]
for name in ['trojan','vmess','shadowsocks2022-default','shadowsocks2022-pmtu']:
    path=W/(name+'-result.json');rows=json.loads(path.read_text())
    assert rows[-1]['event']=='complete'
    stages={x['stage']:x for x in rows if x['event']=='transition-recovered'}
    samples=[x for x in rows if x['event']=='sample']
    expected='failed' if name.endswith('-default') else 'passed'
    assert rows[-1]['result']==expected
    if expected=='passed':
        assert set(stages)=={'wifi-baseline','cellular','wifi','after-unlock'}
        assert len({x['runtime'] for x in samples})==1
        assert all(x['result']=='passed' and x['retries']==0 for x in stages.values())
        assert sum(x['event']=='lock-interval' and x['seconds']>=15 for x in rows)==1
        assert sum(x['event']=='tcp' for x in rows)==12
        assert sum(x['event']=='udp' for x in rows)==8
    result={'name':name,'result':expected,'condition':'IP_MTU_DISCOVER=IP_PMTUDISC_DONT (0) on owned server IPv4 UDP listener only' if name.endswith('-pmtu') else 'server default PMTU policy','recovery':{k:{f:v[f] for f in ['activeRecoverySeconds','secondsSincePathOrUnlock','retries']} for k,v in stages.items()},'lockSeconds':next((x['seconds'] for x in rows if x['event']=='lock-interval'),None),'runtimeStable':len({x['runtime'] for x in samples})==1 if samples else None,'tcpSuccesses':sum(x['event']=='tcp' for x in rows),'udpSuccesses':sum(x['event']=='udp' for x in rows),'udpFailures':[x for x in rows if x['event']=='udp-failed'],'sourceSHA256':hashlib.sha256(path.read_bytes()).hexdigest()}
    results.append(result)
before=json.loads((W/'shadowsocks2022-pmtu-pmtu.json').read_text());after=json.loads((W/'shadowsocks2022-pmtu-pmtu-check.json').read_text())
assert before['before']==1 and before['after']==0 and after['before']==0 and after['after']==0 and after['checkOnly']
assert (before['pid'],before['fd'])==(after['pid'],after['fd'])
summary={'candidate':'5b61eee201fac8639cb1dac0349e34af65db90f7','candidateTree':'5f24e2368eb5c8ee34ae534de652a0f515dc6bb8','manualActions':'completed by owner','results':results,'ss2022DefaultPolicy':'failed; preserved, not waived or fixed','runtimeSemantics':'Fresh TCP/UDP traffic recovered without runtime restart; no claim of established TCP-session survival','serverReferenceCommit':'5ca6f4b7d4dc20a881d4330e498892697627ec0c','serverReferenceSHA256':before['executableSha256'],'pmtuAuditBeforeAndAfterPassed':True,'acceptance':'conditional SS2022 deployment evidence; release qualification still incomplete'}
(W/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
