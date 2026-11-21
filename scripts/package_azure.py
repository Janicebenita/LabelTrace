"""Build a source ZIP for App Service. No Docker image, secrets, or local DB."""
from pathlib import Path
import zipfile

def package(root, output):
    root=Path(root).resolve();output=Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    files=[]
    for folder in ('backend','migrations','fixtures','scripts'):
        for p in (root/folder).rglob('*'):
            parts=p.relative_to(root).parts
            if p.is_file() and not any(x in {'__pycache__','tests','node_modules','.git','.venv','.test-tmp'} or x.startswith('.env') for x in parts) and p.suffix.lower() not in {'.db','.sqlite','.sqlite3','.key','.pem','.pfx','.log'}:
                files.append(p)
    files += [root/x for x in ('alembic.ini','manage.py')]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        # Azure source deployment continues to use the complete Azure/local
        # dependency set; the root requirements.txt is now Vercel-specific.
        archive.writestr('requirements.txt','-r backend/requirements-lock.txt\n')
        for p in files:
            archive.write(p,p.relative_to(root))
    return output

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='artifacts/azure/appservice-source.zip')
    args=p.parse_args()
    print(package(Path(__file__).resolve().parents[1],args.output))
