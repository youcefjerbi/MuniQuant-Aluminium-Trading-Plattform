def test_locations_dependencies_filters_and_provenance(client,core,example):
    e,_,d,_=example
    b=core.post('entities',{'name':'Test Refinery','country':'AU','facility_type':'refinery'})
    for entity,lat,lon in [(e,60,8),(b,-25,135)]:
        r=client.post('/api/asset-map/locations',json={'entity_id':entity['id'],'latitude':lat,'longitude':lon,'document_id':d['id']})
        assert r.status_code==201,r.text
    payload={'from_entity_id':b['id'],'to_entity_id':e['id'],'product':'alumina','kind':'material_supply','document_id':d['id'],'valid_from':'2025-01-01','valid_to':'2025-12-31','note':'Test assertion'}
    assert client.post('/api/asset-map/dependencies',json=payload).status_code==201
    result=client.get('/api/asset-map',params={'product':'alumina','as_of':'2025-06-01'}).json()
    assert len(result['nodes'])==2 and len(result['dependencies'])==1
    assert result['dependencies'][0]['document_id']==d['id']
    assert client.get('/api/asset-map',params={'product':'bauxite','as_of':'2025-06-01'}).json()['dependencies']==[]
    assert client.get('/api/asset-map',params={'as_of':'2026-01-01'}).json()['dependencies']==[]
    assert client.post('/api/asset-map/dependencies',json={**payload,'to_entity_id':b['id']}).status_code==422
    assert client.post('/api/asset-map/locations',json={'entity_id':e['id'],'latitude':91,'longitude':0,'document_id':d['id']}).status_code==422
    assert client.post('/api/asset-map/locations',json={'entity_id':e['id'],'latitude':0,'longitude':0,'document_id':'missing'}).status_code==422
    client.headers.pop('Authorization')
    assert client.post('/api/asset-map/dependencies',json=payload).status_code==401

def test_map_has_scoped_tile_permissions_and_missing_locations(client,example):
    report=client.get('/api/asset-map').json()
    assert report['missing_locations']==1 and report['dependencies']==[]
    assert 'tile.openstreetmap.org' not in client.get('/').headers['content-security-policy']
    assert "script-src 'self'" in client.get('/asset-map-view').headers['content-security-policy']
