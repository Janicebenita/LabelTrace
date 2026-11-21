import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
(Path(__file__).resolve().parents[2]/'.test-tmp').mkdir(exist_ok=True)
os.environ["APP_ENV"]="test"
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from backend import db as m
from backend.main import app
from backend.storage import store

@pytest.fixture
def client(tmp_path,monkeypatch):
    postgres_url=os.getenv('TEST_DATABASE_URL')
    admin=None
    schema='lt_test_'+uuid.uuid4().hex
    if postgres_url:
        if not postgres_url.startswith('postgresql'):
            raise RuntimeError('TEST_DATABASE_URL must identify the dedicated PostgreSQL test database')
        admin=create_engine(postgres_url)
        with admin.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine=create_engine(postgres_url,connect_args={'options':f'-csearch_path={schema},public'}).execution_options(schema_translate_map={None:schema})
    else:
        engine=create_engine("sqlite:///"+(tmp_path/"test.db").as_posix(),connect_args={"check_same_thread":False,"timeout":30})
    monkeypatch.setattr(m,"engine",engine)
    monkeypatch.setattr(m,"Session",sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(store,"root",tmp_path/"objects")
    store.root.mkdir()
    monkeypatch.setenv("AI_MODE","deterministic")
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if admin:
        with admin.begin() as connection:connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

def login(client,role):
    password={'author':'author-1234','reviewer':'reviewer-1234','releaser':'releaser-1234'}[role]
    r=client.post('/api/login',json={'email':role+'@labeltrace.demo','password':password})
    assert r.status_code==200,r.text

def state(client):
    r=client.get('/api/workspace');assert r.status_code==200,r.text
    return r.json()

def upload(client,value='200 Research Way, Boston, MA 02110',product='adult',content=None,filename='SYNTHETIC.txt'):
    login(client,'author')
    body=content if content is not None else f'SYNTHETIC DEMONSTRATION\nmanufacturer_address: {value}\n'.encode()
    r=client.post('/api/sources',data={'product':product},files={'file':(filename,body)})
    assert r.status_code==200,r.text
    source=r.json()
    return next(c for c in state(client)['candidates'] if c['source_id']==source['id'])

def change(client,value='200 Research Way, Boston, MA 02110'):
    candidate=upload(client,value)
    login(client,'reviewer')
    assert client.post('/api/candidates/'+candidate['id']+'/review',json={'approve':True}).status_code==200
    login(client,'author')
    r=client.post('/api/changes',json={'candidate_id':candidate['id'],'reason':'Synthetic manufacturer move supported by new specification'})
    assert r.status_code==200,r.text
    c=r.json()
    login(client,'reviewer')
    r=client.post('/api/changes/'+c['id']+'/approve',json={})
    assert r.status_code==200,r.text
    return r.json()

def generate(client,c=None,defect=None):
    login(client,'author')
    label=next(l for l in state(client)['labels'] if l['key']=='adult.box')
    body={'change_id':c['id'] if c else None}
    path='/api/labels/'+label['id']+'/generate'
    if defect:
        path='/api/demo/labels/'+label['id']+'/defect';body['defect']=defect
    r=client.post(path,json=body);assert r.status_code==200,r.text
    return r.json()

def approved_revision(client,c=None):
    r=generate(client,c)
    v=client.post('/api/revisions/'+r['id']+'/validate',json={})
    assert v.status_code==200 and v.json()['passed'],v.text
    login(client,'reviewer')
    a=client.post('/api/revisions/'+r['id']+'/review',json={'approve':True})
    assert a.status_code==200,a.text
    return r
