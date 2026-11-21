from pathlib import Path
import json
import zipfile
from scripts.package_azure import package

def test_real_appservice_package_has_source_build_entrypoints_without_local_data(tmp_path):
    root=Path(__file__).resolve().parents[2]
    output=package(root,tmp_path/'app.zip')
    with zipfile.ZipFile(output) as z:
        names=z.namelist()
        assert {'requirements.txt','backend/main.py','backend/storage.py','backend/azure_auth.py','scripts/azure-start.sh','alembic.ini','migrations/env.py'}<=set(names)
        assert not any('/data/' in '/'+n or '.venv' in n or 'node_modules' in n or '.env' in n or '__pycache__' in n for n in names)
        assert b'backend/requirements-lock.txt' in z.read('requirements.txt')

def test_package_excludes_nested_secrets_and_databases(tmp_path):
    root=tmp_path/'source';root.mkdir()
    for folder in ('backend','migrations','fixtures','scripts'):(root/folder).mkdir()
    for file in ('requirements.txt','alembic.ini','manage.py'):(root/file).write_text('synthetic')
    (root/'backend/main.py').write_text('application source')
    for file in ('.env','database.db','client.key','certificate.pem'):(root/'backend'/file).write_text('TEST SECRET MUST NOT SHIP')
    with zipfile.ZipFile(package(root,tmp_path/'app.zip')) as z:
        assert 'backend/main.py' in z.namelist()
        assert all(b'TEST SECRET' not in z.read(name) for name in z.namelist())

def test_static_frontend_config_never_rewrites_api_to_html():
    root=Path(__file__).resolve().parents[2]
    config=json.loads((root/'frontend/public/staticwebapp.config.json').read_text())
    assert '/api/*' in config['navigationFallback']['exclude']
    assert "connect-src 'self'" in config['globalHeaders']['Content-Security-Policy']
