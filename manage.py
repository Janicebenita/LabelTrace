"""One cross-platform command for direct startup, reset and checks; Docker optional."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
def env_file():
    p=ROOT/'.env'
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip('"'))
env_file()
def run(*args,**kwargs):
    return subprocess.run([str(x) for x in args],check=True,**kwargs)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['start','reset','init','test','migrate'])
    args=parser.parse_args()
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if args.command=='reset':
        from backend.seed import initialize
        if os.getenv('APP_ENV','development') not in {'development','demo','test'}:raise SystemExit('Reset is development/demo/test only')
        initialize(reset=True)
        # Drop/reset rebuilds the schema from current models. Stamp the corresponding baseline.
        run(sys.executable,'-m','alembic','stamp','head')
        print('Synthetic demonstration reset. Restart the backend if it is running.');return
    if args.command=='test':
        run(sys.executable,'-m','pytest','-q','--junitxml=artifacts/backend-test-results.xml')
        run(npm,'test','--','--reporter=json','--outputFile=../artifacts/frontend-test-results.json',cwd=ROOT/'frontend')
        run(npm,'run','build',cwd=ROOT/'frontend');return
    run(sys.executable,'-m','alembic','upgrade','head')
    if args.command=='migrate':return
    from backend.seed import initialize
    initialize()
    if args.command=='init':return
    if not npm:raise SystemExit('Node.js/npm is required. See README.md')
    # A partial node_modules directory is not enough to start Vite. Repair it
    # through the lockfile when the actual executable is missing.
    if not (ROOT/'frontend/node_modules/vite/bin/vite.js').is_file():run(npm,'ci',cwd=ROOT/'frontend')
    backend=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'])
    frontend=subprocess.Popen([npm,'run','dev'],cwd=ROOT/'frontend')
    print('\nLabelTrace: http://127.0.0.1:5173\nAPI docs: http://127.0.0.1:8000/docs\nCtrl+C stops both services.\n')
    try:
        while backend.poll() is None and frontend.poll() is None:time.sleep(1)
    except KeyboardInterrupt:pass
    finally:
        for p in (frontend,backend):
            if p.poll() is None:p.terminate()
        for p in (frontend,backend):
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:p.kill()
if __name__=='__main__':main()
