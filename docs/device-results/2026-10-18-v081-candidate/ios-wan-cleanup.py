import importlib.util,json,pathlib,shlex
R=pathlib.Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('remote',R/'remote.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
code='''import hashlib,json,pathlib,shutil,subprocess
root=pathlib.Path('/tmp/xray-release-081-manual-5b61eee')
assert root.is_dir() and not root.is_symlink()
assert hashlib.sha256((root/'xray').read_bytes()).hexdigest()=='dad34bede2e76f66f3ade83cd1eba71c39bb2a065011528e5571c0638a5f64e1'
names=['trojan','vmess','shadowsocks2022-default','shadowsocks2022-pmtu']
units={n:subprocess.run(['systemctl','is-active','xray-release-081-manual-'+n+'.service'],capture_output=True,text=True).stdout.strip() for n in names}
assert all(v in ['inactive','unknown'] for v in units.values()),units
services={s:subprocess.check_output(['systemctl','show',s,'--property=ActiveState,MainPID,SubState'],text=True) for s in ['xray-apple-device-probe-server.service','xray-xhttp-device-test.service','x-ui.service']}
assert all('ActiveState=active' in v for v in services.values()),services
assert pathlib.Path('/proc/3514103').exists()
shutil.rmtree(root)
print(json.dumps({'fixtureUnits':units,'services':services,'originalProductionXrayPIDStillPresent':True,'temporaryDirectoryRemoved':not root.exists(),'removedDirectory':str(root)},indent=2))
'''
result=m.run('python3 -c '+shlex.quote(code));(R/'ios-wan-manual/cleanup.json').write_text(result.stdout)
print('WAN cleanup verified: temporary directory/keys removed, fixture units inactive, original test services restored, production Xray PID unchanged.')
