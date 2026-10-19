import json,pathlib,statistics,sys
r=pathlib.Path(__file__).resolve().parent;d=r/(sys.argv[1] if len(sys.argv)>1 else 'performance-protocols')
m=json.loads((d/'manifest.json').read_text());raw=[];by={}
for run in m['runs']:
 name=f"{run['case']}-{run['version']}-{run['repeat']}";p=d/name/'result.json'
 if not p.exists():continue
 result=json.loads(p.read_text());assert result['status']=='pass' and run['returncode']==0 and not run['surviving_process_group']
 row={'case':run['case'],'version':run['version'],'repeat':run['repeat'],'order':run['order'],'ambient':run['ambient_cpu'],'processGroupEmpty':run['process_group_empty_after_run'],'result':result}
 raw.append(row);by[(run['case'],run['version'],run['repeat'])]=result
profiles=['trojan-tls','ss2022-aes128','ss2022-aes256','ss2022-chacha20','vmess-aes128','vmess-chacha20','vmess-auto'];comparisons=[]
for profile in profiles:
 try:
  throughput={v:[by[(profile+'-socks-full-duplex-1',v,k)]['throughput_mib_s'] for k in range(1,6)] for v in ['candidate','baseline','xray']}
  latency={v:[by[(profile+'-socks-tcp-latency-1',v,k)]['latency_us']['p95'] for k in range(1,6)] for v in ['candidate','baseline','xray']}
  memory={v:[max(by[(profile+'-socks-'+work+'-1',v,k)]['peak_rss_kib'] for work in ['full-duplex','tcp-latency'])/1024 for k in range(1,6)] for v in ['candidate','baseline','xray']}
 except KeyError:continue
 ratios={metric:{v:[x/y for x,y in zip(values['candidate'],values[v])] for v in ['baseline','xray']} for metric,values in [('throughput',throughput),('latency',latency),('memory',memory)]}
 checks={'throughputVsBaseline':statistics.median(ratios['throughput']['baseline'])>=.95,'latencyVsBaseline':statistics.median(ratios['latency']['baseline'])<=1.05,'memoryVsBaseline':statistics.median(ratios['memory']['baseline'])<=1.05,'throughputVsXray':statistics.median(ratios['throughput']['xray'])>=.5,'latencyVsXray':statistics.median(ratios['latency']['xray'])<=2,'memoryWithin64MiB':statistics.median(memory['candidate'])<=64}
 comparisons.append({'profile':profile,'throughputMiBs':throughput,'p95LatencyUs':latency,'sampledPeakRSSMiB':memory,'pairedRatios':ratios,'checks':checks})
measurements=[]
for protocol,selected in [('trojan',['trojan-tls']),('shadowsocks2022',['ss2022-aes128','ss2022-aes256','ss2022-chacha20']),('vmess',['vmess-aes128','vmess-chacha20','vmess-auto'])]:
 rows=[v for v in comparisons if v['profile'] in selected]
 if len(rows)!=len(selected):continue
 for metric,unit,comparison,threshold in [('throughput','% of paired Xray throughput','at-least',50),('latency','% of paired Xray p95 latency','at-most',200),('memory','MiB sampled peak RSS','at-most',64)]:
  samples=[]
  for k in range(5):
   values=[v['sampledPeakRSSMiB']['candidate'][k] if metric=='memory' else 100*v['pairedRatios'][metric]['xray'][k] for v in rows]
   samples.append(min(values) if metric=='throughput' else max(values))
  measurements.append({'id':protocol+'-'+metric,'unit':unit,'samples':samples,'comparison':comparison,'threshold':threshold})
out={'complete':m.get('status')=='pass' and len(raw)==210,'trialCount':len(raw),'profiles':comparisons,'schema4Measurements':measurements,'fivePercentAllProfilesPassed':len(comparisons)==7 and all(v for c in comparisons for k,v in c['checks'].items() if k.endswith('Baseline')),'scope':'Single-flow loopback SOCKS, five rotating-order paired repetitions; native release profile. Original outliers retained.'}
(d/'benchmark-raw.json').write_text(json.dumps(raw,indent=2)+'\n');(d/'protocol-comparisons.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'complete':out['complete'],'trials':len(raw),'fivePercentAllProfilesPassed':out['fivePercentAllProfilesPassed'],'profiles':[{'profile':c['profile'],'baselineMedians':{k:statistics.median(v['baseline']) for k,v in c['pairedRatios'].items()},'checks':c['checks']} for c in comparisons]},indent=2))
