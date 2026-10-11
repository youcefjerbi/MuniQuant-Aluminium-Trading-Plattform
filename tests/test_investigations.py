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

def test_task_answer_requires_local_evidence_and_preserves_revision(client):
    c=make(client)
    c=revise(client,c,task={'question':'Is backup power available?','assignee':'Analyst','due_at':'2026-01-01T12:00:00Z'}).json()
    t=c['snapshot']['tasks'][0]
    assert t['created_by']=='local-curator' and t['status']=='open'
    assert revise(client,c,task={**{k:t[k] for k in ['id','question','assignee','due_at','status','answer','evidence_entry_ids']},'status':'answered','answer':'Yes'}).status_code==422
    c=revise(client,c,entry={'kind':'evidence','text':'Operator notice','source_url':'https://example.org/notice'}).json()
    task={'id':t['id'],'question':t['question'],'status':'answered','answer':'Backup power confirmed in notice','evidence_entry_ids':[c['snapshot']['entries'][0]['id']]}
    assert revise(client,c,task={**task,'evidence_entry_ids':['foreign-entry']}).status_code==422
    c=revise(client,c,task=task).json()
    assert c['snapshot']['tasks'][0]['status']=='answered'
    history=client.get('/api/investigations/'+c['id']).json()['revisions']
    assert history[1]['snapshot']['tasks'][0]['status']=='open'
    c=revise(client,c,task={**task,'status':'open'}).json()
    assert c['snapshot']['tasks'][0]['created_at']==t['created_at']
    assert revise(client,c,task={**task,'id':'missing'}).status_code==422

def test_evidence_hypothesis_link_and_publication_chronology(client):
    c=make(client)
    c=revise(client,c,entry={'kind':'hypothesis','text':'Production interruption'}).json()
    h=c['snapshot']['entries'][0]['id']
    entry={'kind':'evidence','text':'Operator statement','source_url':'https://example.org/notice','hypothesis_id':h,'stance':'contradicts','passage':'Backup generation maintained operations.','published_at':'2026-01-01T12:00:00Z'}
    assert revise(client,c,entry={**entry,'hypothesis_id':'other-case'}).status_code==422
    assert revise(client,c,entry={**entry,'published_at':'bad'}).status_code==422
    c=revise(client,c,entry=entry).json()
    assert c['snapshot']['entries'][1]['stance']=='contradicts'
    assert c['snapshot']['entries'][1]['passage']==entry['passage']
