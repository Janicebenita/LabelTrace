"""Offline contract tests: these do NOT establish live Azure connectivity."""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from backend.storage import AzureBlobStorage, LocalStorage, build_storage, digest
from backend.azure_assistance import read_document, explain_change, azure_structured
from backend.azure_auth import postgres_connect_parameters, POSTGRES_SCOPE
from backend import workflow as w
from conftest import login, state, upload, change

def blob_store():
    container=Mock();client=Mock();client.get_container_client.return_value=container
    return AzureBlobStorage('https://synthetic.blob.core.windows.net','labeltrace-private',client),container

def test_blob_create_only_upload_and_idempotent_verification():
    storage,c=blob_store();data=b'%PDF synthetic';key=storage.put(data,'.pdf')
    assert key==digest(data)+'.pdf'
    assert c.upload_blob.call_args.kwargs['overwrite'] is False
    c.upload_blob.side_effect=ResourceExistsError('exists')
    c.download_blob.return_value.readall.return_value=data
    assert storage.put(data,'.pdf')==key
    c.download_blob.return_value.readall.return_value=b'wrong bytes'
    with pytest.raises(OSError,match='content-addressed'):storage.put(data,'.pdf')

@pytest.mark.parametrize('key',['../secret.txt','https://private/file.pdf','0'*64+'.exe','x.pdf'])
def test_both_storage_adapters_reject_untrusted_keys(tmp_path,key):
    storage,_=blob_store()
    for backend in (storage,LocalStorage(tmp_path)):
        with pytest.raises(ValueError):backend.get(key)

def test_blob_missing_and_private_health_gate():
    storage,c=blob_store();c.download_blob.side_effect=ResourceNotFoundError('missing')
    with pytest.raises(FileNotFoundError):storage.get('0'*64+'.pdf')
    c.get_container_properties.return_value={'public_access':None};storage.healthcheck()
    c.get_container_properties.return_value={'public_access':'blob'}
    with pytest.raises(OSError,match='anonymous'):storage.healthcheck()

def test_unknown_storage_backend_does_not_fall_back(monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND','typo')
    with pytest.raises(ValueError):build_storage()
    monkeypatch.setenv('STORAGE_BACKEND','local');monkeypatch.setenv('APP_ENV','production')
    with pytest.raises(ValueError,match='production|Production'):build_storage()

def test_postgres_identity_token_renewal_and_tls(monkeypatch):
    monkeypatch.setenv('PGHOST','synthetic.postgres.database.azure.com');monkeypatch.setenv('PGUSER','labeltrace-api')
    identity=Mock();identity.get_token.side_effect=[SimpleNamespace(token='token-one'),SimpleNamespace(token='token-two')]
    with patch('backend.azure_auth.credential',return_value=identity):
        first=postgres_connect_parameters();second=postgres_connect_parameters()
    assert first['password']=='token-one' and second['password']=='token-two'
    assert first['sslmode']=='verify-full'
    identity.get_token.assert_called_with(POSTGRES_SCOPE)

def test_azure_openai_structured_identity_request(monkeypatch):
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT','https://synthetic.openai.azure.com')
    monkeypatch.setenv('AZURE_OPENAI_DEPLOYMENT','approved-model')
    monkeypatch.delenv('AZURE_OPENAI_API_KEY',raising=False)
    response=Mock();response.json.return_value={'choices':[{'message':{'content':'{"facts":[]}'}}]}
    with patch('backend.azure_assistance.auth_headers',return_value={'Authorization':'Bearer test-token'}),patch('backend.azure_assistance.httpx.post',return_value=response) as post:
        assert azure_structured([],{'type':'object'},'test')=={'facts':[]}
    assert post.call_args.kwargs['follow_redirects'] is False
    assert post.call_args.kwargs['json']['response_format']['type']=='json_schema'
    assert 'api-key' not in post.call_args.kwargs['headers']

def test_azure_model_duplicate_or_invented_fact_rejected(monkeypatch):
    monkeypatch.setenv('AI_MODE','azure_openai')
    pages=['manufacturer_name: Synthetic Devices\nmanufacturer_address: Synthetic Address\n']
    invented=[{'field':'manufacturer_name','value':'Synthetic Devices','page':1,'quote':'Synthetic Devices'}]*2
    with patch('backend.azure_assistance.suggest_facts',return_value=invented):
        facts,mode,warning=w.extract(pages)
    assert len(facts)==2 and warning and 'Deterministic' in mode
    with patch('backend.azure_assistance.suggest_facts',side_effect=TimeoutError('offline')):
        assert w.extract(pages)[2]

def test_azure_model_grounded_success_remains_advisory(monkeypatch):
    pages=['manufacturer_address: Approved Demo Address\n']
    facts,_,_=w.extract(pages)
    suggestion=[{k:x[k] for k in ('field','value','page','quote')} for x in facts]
    monkeypatch.setenv('AI_MODE','azure_openai')
    with patch('backend.azure_assistance.suggest_facts',return_value=suggestion):
        actual,mode,warning=w.extract(pages)
    assert actual==facts and warning is None and 'human review' in mode

def test_document_intelligence_bounded_transcript_and_redirect_rejection(monkeypatch):
    monkeypatch.setenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT','https://synthetic.cognitiveservices.azure.com')
    monkeypatch.setenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY','test-only')
    def transport(request):
        if request.method=='POST':
            return httpx.Response(202,headers={'operation-location':'https://synthetic.cognitiveservices.azure.com/documentintelligence/operations/123'})
        return httpx.Response(200,json={'status':'succeeded','analyzeResult':{'pages':[{'lines':[{'content':'manufacturer_address: Synthetic Address'}]}]}})
    with httpx.Client(transport=httpx.MockTransport(transport)) as c:
        pages,proof=read_document(b'%PDF-synthetic',client=c)
    assert pages==['manufacturer_address: Synthetic Address'] and len(proof['result_sha256'])==64
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(202,headers={'operation-location':'https://untrusted.example/operation'}))) as c:
        with pytest.raises(ValueError,match='Untrusted'):read_document(b'%PDF-synthetic',client=c)

def test_document_intelligence_outage_falls_back_for_text_pdf(client,monkeypatch):
    monkeypatch.setenv('DOCUMENT_EXTRACTOR','azure_document_intelligence')
    from backend.db import ROOT
    with patch('backend.azure_assistance.read_document',side_effect=TimeoutError('offline')):
        candidate=upload(client,content=(ROOT/'fixtures/SYNTHETIC-adult-spec-v2.pdf').read_bytes(),filename='SYNTHETIC.pdf')
    source=next(s for s in state(client)['sources'] if s['id']==candidate['source_id'])
    assert 'local text-based extraction used' in source['warning']

def test_explanation_uses_only_known_source_and_change(client,monkeypatch):
    c=change(client);r=client.get('/api/changes/'+c['id']+'/explanation')
    assert r.status_code==200 and 'Deterministic' in r.json()['mode']
    assert c['source_id'] in r.json()['explanation']
    monkeypatch.setenv('AI_MODE','azure_openai')
    with patch('backend.azure_assistance.azure_structured',return_value={'source_id':'invented','change_id':c['id'],'reason_code':'explicit_fact_dependency'}):
        r=client.get('/api/changes/'+c['id']+'/explanation')
    assert r.json()['warning'] and r.json()['source_id']==c['source_id']

def test_health_checks_and_authenticated_downloads(client):
    assert client.get('/api/health/live').status_code==200
    assert client.get('/api/health/ready').json()['storage']=='local'
    assert client.get('/api/files/source/unknown').status_code==401
    with patch('backend.main.store.healthcheck',side_effect=OSError('storage unavailable')):
        assert client.get('/api/health/ready').status_code==503
        assert client.get('/api/health/live').status_code==200

def test_cloud_seed_has_no_committed_default_password(client,monkeypatch):
    from backend.seed import seed
    monkeypatch.setenv('APP_ENV','production')
    with patch('backend.seed.m.rows',return_value=[]):
        with pytest.raises(RuntimeError,match='default demo credentials'):seed(Mock())
