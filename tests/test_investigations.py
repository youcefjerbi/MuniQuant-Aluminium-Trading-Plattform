def make(client,**values):
    r=client.post('/api/investigations',json={'title':'Power disruption',**values})
    assert r.status_code==201,r.text
    return r.json()

def revise(client,c,**values):
    return client.post('/api/investigations/'+c['id']+'/revisions',json={'expected_version':c['version'],**values})

def test_manual_case_independent_history_and_source_validation(client,example):
    e,_,d,_=example
    c=make(client,asset_ids=[e['id']],owner='Analyst')
    assert c['status']=='investigating' and c['version']==1
    assert revise(client,c,entry={'kind':'evidence','text':'Unreferenced claim'}).status_code==422
    assert revise(client,c,entry={'kind':'evidence','text':'Bad document','document_id':'missing'}).status_code==422
    r=revise(client,c,entry={'kind':'evidence','text':'Recorded facility notice','document_id':d['id']})
    assert r.status_code==201
    updated=r.json()
    assert revise(client,c,owner='Stale edit').status_code==409
    assert revise(client,updated,status='confirmed').status_code==422
    updated=revise(client,updated,entry={'kind':'conclusion','text':'Analyst confirmed interruption'}).json()
    updated=revise(client,updated,status='confirmed').json()
    detail=client.get('/api/investigations/'+c['id']).json()
    assert len(detail['revisions'])==4 and detail['revisions'][0]['snapshot']['entries']==[]
    assert detail['revisions'][1]['snapshot']['entries'][0]['document_id']==d['id']
    assert updated['status']=='confirmed'
    assert client.get('/api/investigations',params={'status':'confirmed'}).json()[0]['id']==c['id']
    assert client.get('/api/leads').json()['leads']==[]

def test_validation_and_access(client):
    assert client.post('/api/investigations',json={'title':' '}).status_code==422
    assert client.post('/api/investigations',json={'title':'X','asset_ids':['missing']}).status_code==422
    assert client.post('/api/investigations',json={'title':'X','review_at':'2026-10-12'}).status_code==422
    c=make(client)
    assert revise(client,c,entry={'kind':'evidence','text':'Unsafe','source_url':'javascript:alert(1)'}).status_code==422
    assert client.get('/api/investigations/missing').status_code==404
    client.headers.pop('Authorization')
    assert client.post('/api/investigations',json={'title':'Unauthorized'}).status_code==401
    assert revise(client,c,owner='Unauthorized').status_code==401

def test_conclusion_does_not_confirm_unsourced_case(client):
    c=make(client)
    c=revise(client,c,entry={'kind':'conclusion','text':'Unproven judgment'}).json()
    assert revise(client,c,status='confirmed').status_code==422
    c=revise(client,c,status='inconclusive').json()
    assert c['status']=='inconclusive'
    assert revise(client,c,status='investigating').status_code==201
