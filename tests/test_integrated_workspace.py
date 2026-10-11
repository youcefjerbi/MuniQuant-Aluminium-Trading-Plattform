def test_all_feature_sections_are_wired_and_available(client):
    root=client.get('/').text
    for name in ['asset-map','market','investigations']:
        assert '/static/'+name+'.js' in root
    for section in ['map','research','investigations']:
        assert 'data-page="'+section+'"' in root
    for route in ['/api/asset-map','/api/research','/api/investigations']:
        assert client.get(route).status_code==200
    assert client.get('/asset-map-view').status_code==200
