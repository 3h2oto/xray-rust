#!/usr/bin/env python3
import copy, hashlib, importlib.util, json, os, pathlib, shutil, statistics, time
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("comparison", ROOT/"scripts/run-v08-protocol-comparison.py")
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
b=c.bench
os.umask(0o077)
for key in ("GOMAXPROCS","TOKIO_WORKER_THREADS","GOMEMLIMIT","GOGC"):
    os.environ.pop(key,None)
out=ROOT/"target/release-081/performance-ss2022-latency-followup"
out.mkdir(exist_ok=False)
paths={"candidate":ROOT/"target/release-081/host-cargo/release/xray-rust",
       "harness":ROOT/"target/release-081/host-cargo/release/xray-bench",
       "baseline":ROOT/"target/release-081/baseline-cargo/release/xray-rust",
       "xray":ROOT/"target/issue69-tvos/xray-reference"}
c.device.verify_reference(paths["xray"])
assert not b.command(["git","status","--porcelain"],ROOT)
assert not c.ambient()["compiler_load_detected"], "wait until builds finish"
manifest={"candidate":{"revision":b.command(["git","rev-parse","HEAD"],ROOT),"tree":b.command(["git","rev-parse","HEAD^{tree}"],ROOT),"dirty":False},
          "profile":"release", "clean":True, "repeats":15,
          "binarySha256":{k:b.sha(v) for k,v in paths.items()},
          "referenceCommit":b.REFERENCE,"collectorSha256":b.sha(__file__),
          "scope":"Diagnostic follow-up of original SS2022 ChaCha20 p95 failure: 15 fresh rotating-order candidate/baseline pairs; original failure is retained",
          "regressionBudgets":{"throughputMinimumFraction":0.95,"latencyMaximumFraction":1.05,"memoryMaximumFraction":1.05},
          "started":time.time(),"runs":[]}
b.save(out/"manifest.json",manifest)
launcher=out/"xray-client"
shutil.copyfile(ROOT/"scripts/v08-reference-client.py",launcher);launcher.chmod(0o700)
b.save(pathlib.Path(str(launcher)+".json"),{"mode":"xray","binaries":{"xray":str(paths["xray"])}})
cases=[x for x in c.cases(c.PROFILES) if x["profile"]=="ss2022-chacha20" and x["connections"]==1 and x["traffic"]=="tcp-latency"]
assert len(cases)==1
for index,case in enumerate(cases):
    for repeat in range(1,16):
        assert not c.ambient()["compiler_load_detected"], "compiler activity"
        order=["candidate","baseline"]
        offset=(index+repeat-1)%len(order)
        order=order[offset:]+order[:offset]
        with c.fixture(paths["xray"],out/f"{case['id']}-server-{repeat}",case["profile"]) as (config,pid):
            os.environ["BENCH_REFERENCE_CERT"]=str(out/f"{case['id']}-server-{repeat}/tls.crt")
            for version in order:
                name=f"{case['id']}-{version}-{repeat}"
                request={k:case[k] for k in ("path","traffic","connections","iterations","payload_size")}
                request.update(binary=str(launcher if version=="xray" else paths[version]), config=copy.deepcopy(config), output=str(out/name), warmup=True,prepare_client=version=="xray",client_preface=case["traffic"]!="tcp-latency")
                b.save(out/(name+".json"),request)
                run=c.measured_execute([str(paths["harness"]),"protocol-run",str(out/(name+".json"))],out/(name+".log"))
                run.update(case=case["id"],version=version,repeat=repeat,order=order)
                manifest["runs"].append(run);b.save(out/"manifest.json",manifest)
                print(name,run["returncode"],round(run["seconds"],2),flush=True)
                assert run["returncode"]==0 and not run["surviving_process_group"]
                assert not run["ambient_cpu"]["compiler_load_detected"]
manifest.update(finished=time.time(),status="pass")
b.save(out/"manifest.json",manifest)
