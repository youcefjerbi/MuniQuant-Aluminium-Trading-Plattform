"""MuniQuant Workspace: leads, research and practice trading, investigations and the map.

Plants, companies, sources, documents and facts come from the Data Core through its API
(app.core_client); the Workspace stores Core IDs and asks the Core for details."""
import json
import logging
import os
import secrets
import time
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import make_engine, DATABASE_URL
from .models import Audit
from .services import record
from .core_client import CoreClient, CoreUnavailable

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('muniquant')
STATIC=Path(__file__).parent/'static'

def create_app(database_url=None, storage=None, write_token=None, core=None):
    Path('data').mkdir(exist_ok=True)
    app=FastAPI(title='MuniQuant Workspace', version='1.0.0')
    app.state.engine=make_engine(database_url or DATABASE_URL)
    app.state.core=core or CoreClient()
    # Where people open the Core's own screens; the server may reach the Core under another address.
    app.state.core_public_url=os.getenv('CORE_PUBLIC_URL',app.state.core.base_url)
    app.state.storage=Path(storage or os.getenv('SNAPSHOT_DIR','data/snapshots'))
    app.state.write_token=write_token if write_token is not None else os.getenv('WRITE_TOKEN','')
    app.state.actor=os.getenv('WRITE_ACTOR','local-curator')
    app.state.require_read_auth=os.getenv('REQUIRE_READ_AUTH','false').lower()=='true'
    app.state.read_token=os.getenv('READ_TOKEN','')


    def session():
        with Session(app.state.engine) as s:
            yield s

    def core():
        # One cached view per request: each Core list is read at most once.
        return app.state.core.cached()

    def writer(request:Request):
        token=request.headers.get('authorization','').removeprefix('Bearer ')
        identities=json.loads(os.getenv('WRITE_IDENTITIES_JSON') or '{}')
        for credential,identity in identities.items():
            if secrets.compare_digest(token,credential):
                return identity
        if not app.state.write_token or not secrets.compare_digest(token, app.state.write_token):
            raise HTTPException(401,'Set WRITE_TOKEN on the server and enter it in Workspace access to edit')
        return app.state.actor

    def get(s, model, identifier):
        obj=s.get(model, identifier)
        if not obj: raise HTTPException(404,'Record not found')
        return obj

    def audit(s, actor, action, obj):
        s.flush(); s.add(Audit(actor=actor, action=action, record_id=obj.id, detail={'type':obj.__tablename__}))

    @app.middleware('http')
    async def request_log(request, call_next):
        start=time.monotonic()
        if app.state.require_read_auth and (request.method=='GET' or request.url.path in ('/api/chat','/api/chat/stream')) and request.url.path.startswith('/api/') and request.url.path!='/api/health':
            token=request.headers.get('authorization','').removeprefix('Bearer ')
            allowed=[app.state.write_token,app.state.read_token,*json.loads(os.getenv('WRITE_IDENTITIES_JSON') or '{}')]
            if not token or not any(credential and secrets.compare_digest(token,credential) for credential in allowed):
                return JSONResponse({'detail':'Workspace read authorization required'},status_code=401)
        # Guard both declared and streamed bodies before JSON parsing.
        if request.method in ('POST','PUT','PATCH'):
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>14_000_000: return JSONResponse({'detail':'Request exceeds 14 MB'},status_code=413)
            request._body=bytes(body)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers.setdefault('Referrer-Policy','same-origin')
        if request.url.path in ('/','/static/app.js','/static/style.css'):
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self' https://www.tradingview-widget.com; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        logger.info(json.dumps({'method':request.method,'path':request.url.path,'status':response.status_code,'duration_ms':round((time.monotonic()-start)*1000)}))
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc): return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(CoreUnavailable)
    async def core_unavailable(request, exc): return JSONResponse({'detail':str(exc)},status_code=503)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc): return JSONResponse({'detail':'Conflicting record or invalid reference; refresh and retry'},status_code=409)

    from sqlalchemy.exc import OperationalError
    @app.exception_handler(OperationalError)
    async def busy(request, exc):
        if 'locked' not in str(exc.orig).lower(): raise exc
        return JSONResponse({'detail':'The database is busy with another write; retry in a moment'},status_code=503)

    from .investigations import Investigation, InvestigationRevision, CaseIn, RevisionIn, CaseConflict
    from . import investigations

    @app.exception_handler(CaseConflict)
    async def case_conflict(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=409)

    @app.get('/api/investigations')
    def cases(status:str|None=Query(None,pattern='^(investigating|confirmed|disproven|resolved|inconclusive)$'),
              offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),s:Session=Depends(session)):
        query=select(Investigation)
        if status: query=query.where(Investigation.status==status)
        return [record(c) for c in s.scalars(query.order_by(Investigation.updated_at.desc(),Investigation.id).offset(offset).limit(limit))]

    @app.post('/api/investigations',status_code=201)
    def create_case(data:CaseIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        c=investigations.create(s,data,actor,core);audit(s,actor,'investigation_created',c);s.commit();return record(c)

    @app.get('/api/investigations/{identifier}')
    def case_detail(identifier:str,s:Session=Depends(session)):
        c=get(s,Investigation,identifier)
        return {'case':record(c),'revisions':[record(r) for r in s.scalars(select(InvestigationRevision)
            .where(InvestigationRevision.case_id==identifier).order_by(InvestigationRevision.version))]}

    @app.get('/api/investigations/{identifier}/notebook')
    def case_notebook(identifier:str,s:Session=Depends(session)):
        get(s,Investigation,identifier)
        from .investigations import InvestigationEntry, InvestigationTask, InvestigationTaskEvidence
        entries=[record(e) for e in s.scalars(select(InvestigationEntry).where(InvestigationEntry.case_id==identifier)
            .order_by(InvestigationEntry.recorded_at,InvestigationEntry.id))]
        tasks=[record(t) for t in s.scalars(select(InvestigationTask).where(InvestigationTask.case_id==identifier)
            .order_by(InvestigationTask.created_at,InvestigationTask.id))]
        for task in tasks:
            task['evidence_entry_ids']=list(s.scalars(select(InvestigationTaskEvidence.entry_id)
                .where(InvestigationTaskEvidence.task_id==task['id']).order_by(InvestigationTaskEvidence.entry_id)))
        return {'entries':entries,'tasks':tasks}

    @app.post('/api/investigations/{identifier}/revisions',status_code=201)
    def revise_case(identifier:str,data:RevisionIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        c=investigations.revise(s,get(s,Investigation,identifier),data,actor,core)
        audit(s,actor,'investigation_revised',c);s.commit();return record(c)

    from .asset_map import LocationIn, DependencyIn, AssetLocation, AssetDependency
    from . import asset_map
    from datetime import date

    @app.get('/api/asset-map')
    def asset_graph(product:str|None=Query(None,pattern='^(bauxite|alumina|primary_aluminium|electricity|other)$'),as_of:date|None=None,s:Session=Depends(session),core=Depends(core)):
        return asset_map.graph(s,core,product,as_of)

    @app.post('/api/asset-map/locations',status_code=201)
    def asset_location(data:LocationIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        values=data.model_dump();asset_map.validate_references(core,values)
        obj=AssetLocation(**values,actor=actor);s.add(obj);audit(s,actor,'asset_location',obj);s.commit();return record(obj)

    @app.post('/api/asset-map/dependencies',status_code=201)
    def asset_dependency(data:DependencyIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        values=data.model_dump(mode='json');asset_map.validate_references(core,values)
        obj=AssetDependency(**values,actor=actor);s.add(obj);audit(s,actor,'asset_dependency',obj);s.commit();return record(obj)

    @app.get('/asset-map-view')
    def map_view():
        response=FileResponse(STATIC/'asset-map-view.html')
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        return response

    from . import chatbot

    @app.get('/api/chat/status')
    def chat_status():
        return {'ai_available':chatbot.ai_enabled(), 'default_mode':'local'}

    @app.post('/api/chat')
    def chat(data:chatbot.ChatIn,request:Request,s:Session=Depends(session),core=Depends(core)):
        if data.use_ai:
            writer(request)  # Paid provider access requires an attributable workspace identity.
            if not chatbot.ai_enabled():
                raise HTTPException(503,'AI summaries are not configured; use local mode')
        return chatbot.answer(s,data,core)

    @app.post('/api/chat/stream')
    def chat_stream(data:chatbot.ChatIn,request:Request,s:Session=Depends(session),core=Depends(core)):
        if data.use_ai:
            writer(request)
            if not chatbot.ai_enabled():
                raise HTTPException(503,'AI summaries are not configured; use local mode')
        scope, sources = chatbot.retrieve(s,data,core)
        return StreamingResponse(chatbot.stream_answer(data,scope,sources), media_type='text/event-stream',
            headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

    @app.get('/api/health')
    def health(s:Session=Depends(session)):
        s.execute(text('SELECT 1'))
        # The Workspace runs without the Core; Core-backed pages then report it unavailable.
        try: connected={'status':'ok' if app.state.core.health().get('status')=='ok' else 'unavailable'}
        except (CoreUnavailable,ValueError) as exc: connected={'status':'unavailable','detail':str(exc)}
        return {'status':'ok','version':'1.0.0','scope':'workspace','core':{'url':app.state.core_public_url,**connected}}

    # Data Core reads for the screens; the Core stays the source of truth.
    @app.get('/api/core/catalog')
    def core_catalog(core=Depends(core)):
        return {'core_url':app.state.core_public_url,'entities':core.entities(),'documents':core.documents(),'sources':core.sources(),'observations':core.observations()}

    @app.get('/api/core/documents/{identifier}/content')
    def core_document_content(identifier:str,core=Depends(core)):
        return Response(core.document_content(identifier),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{identifier}.txt"'})

    @app.get('/api/core/observations')
    def core_observations(document_id:str=Query(min_length=1,max_length=100),core=Depends(core)):
        return core.observations(document_id=document_id)

    from .schemas import ProposalIn
    @app.post('/api/core/proposals',status_code=201)
    def core_proposal(data:ProposalIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        # A candidate fact: the Core checks the source, matches the plant, checks quality and decides.
        result=core.propose_fact(data.document_id,data.extraction)
        s.add(Audit(actor=actor,action='core_proposal',record_id=result['build']['id'],detail={'document_id':data.document_id,'candidates':[{'id':c['id'],'status':c['status'],'observation_id':c['observation_id'],'review_id':c['review_id']} for c in result['candidates']]}))
        s.commit()
        return result

    @app.get('/api/records/{record_type}')
    def records(record_type:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=1000),s:Session=Depends(session)):
        from sqlalchemy import func
        from .models import Lead,LeadRevision,LeadHeadline,LeadSource,LeadSourceAccess,LeadDocument,LeadRun,LeadRetrievalAttempt
        models={'leads':Lead,'lead_revisions':LeadRevision,'lead_headlines':LeadHeadline,'lead_sources':LeadSource,'lead_source_access':LeadSourceAccess,
                'lead_documents':LeadDocument,'lead_runs':LeadRun,'lead_retrieval_attempts':LeadRetrievalAttempt,'audit':Audit}
        model=models.get(record_type)
        if model is None: raise HTTPException(404,'Unknown record type')
        return {'records':[record(o) for o in s.scalars(select(model).order_by(model.id).offset(offset).limit(limit))],'total':s.scalar(select(func.count()).select_from(model)),'offset':offset,'limit':limit}

    # Licensed Permutable feed: lead-only, factual events/headlines, never exported as evidence.
    from .schemas import PermutableSourceIn,PermutableCaptureIn,LeadDecisionIn,SourceAccessIn
    from . import permutable

    @app.post('/api/permutable/source',status_code=201)
    def permutable_source(data:PermutableSourceIn,s:Session=Depends(session),actor=Depends(writer)):
        source,policy=permutable.register_source(s,actor,data)
        return {'source':record(source),'access':record(policy)}

    @app.post('/api/permutable/access',status_code=201)
    def permutable_access(data:SourceAccessIn,s:Session=Depends(session),actor=Depends(writer)):
        try: return record(permutable.record_access(s,actor,data))
        except LookupError as exc: raise HTTPException(404,str(exc))

    @app.post('/api/permutable/capture')
    def permutable_capture(data:PermutableCaptureIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        result=permutable.capture(s,app.state.storage,actor,data,core)
        if data.feed in ('events','event_headlines'):
            try:
                result['research_bridge']=research.import_leads(s,actor,core,result['document_ids'],live=data.mode=='live')
            except (ValueError,LookupError,CoreUnavailable) as exc:
                s.rollback()
                result['research_bridge']={'status':'blocked','reason':str(exc)}
        return result

    @app.post('/api/permutable/documents/{identifier}/replay')
    def permutable_replay(identifier:str,s:Session=Depends(session),actor=Depends(writer)):
        return permutable.replay_document(s,app.state.storage,identifier)

    @app.get('/api/permutable/documents/{identifier}/content')
    def permutable_content(identifier:str,s:Session=Depends(session)):
        from .models import LeadDocument
        from .pipeline import snapshot_bytes
        doc=get(s,LeadDocument,identifier)
        try: raw=snapshot_bytes(app.state.storage,doc)
        except ValueError as exc: raise HTTPException(409,str(exc))
        return Response(raw,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{doc.content_hash}.txt"'})

    @app.get('/api/leads')
    def leads(status:str|None=Query(None,pattern='^(new|follow_up|dismissed|confirmed)$'),topic:str|None=Query(None,max_length=200),matched:bool|None=None,search:str|None=Query(None,max_length=500),
              offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),s:Session=Depends(session),core=Depends(core)):
        from .models import LeadSource
        source=s.get(LeadSource,permutable.SOURCE_ID);policy=permutable.latest_policy(s)
        return {**permutable.list_leads(s,core,status,offset,limit,topic,matched,search),'source_id':permutable.SOURCE_ID,
                'source':record(source) if source else None,'access':record(policy) if policy else None}

    @app.post('/api/leads/{identifier}/decision')
    def lead_decision(identifier:str,data:LeadDecisionIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        try: return record(permutable.decide(s,identifier,data,actor,core))
        except LookupError: raise HTTPException(404,'Lead not found')
        except permutable.LeadConflict as exc: raise HTTPException(409,str(exc))

    from . import research
    from .research_schemas import EventIn, QuoteIn, OutcomeIn, PolicyIn
    from .research_models import ResearchEvent, PaperAccount, PaperPolicy

    @app.exception_handler(research.Conflict)
    async def research_conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.get('/api/research')
    def research_workspace(s:Session=Depends(session)):
        return research.dashboard(s)

    @app.get('/api/research/influence')
    def event_influence(as_of:str|None=Query(None,max_length=40),s:Session=Depends(session)):
        from .event_influence import report
        return report(s,as_of)

    @app.get('/api/research/performance')
    def paper_performance(s:Session=Depends(session)):
        from .paper_performance import performance
        return performance(s)

    @app.post('/api/research/policy')
    def paper_policy(data:PolicyIn,s:Session=Depends(session),actor=Depends(writer)):
        return research.configure(s,data,actor)

    @app.post('/api/research/events',status_code=201)
    def research_event(data:EventIn,s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        try: return research.ingest_event(s,data,actor,core)
        except LookupError as exc: raise HTTPException(404,str(exc))

    @app.post('/api/research/quotes',status_code=201)
    def research_quote(data:QuoteIn,s:Session=Depends(session),actor=Depends(writer)):
        return research.ingest_quote(s,data,actor)

    @app.post('/api/research/outcomes',status_code=201)
    def research_outcome(data:OutcomeIn,s:Session=Depends(session),actor=Depends(writer)):
        try: return research.label_outcome(s,data,actor)
        except LookupError as exc: raise HTTPException(404,str(exc))

    @app.get('/api/research/events/{identifier}/analogues')
    def event_analogues(identifier:str,s:Session=Depends(session)):
        event=get(s,ResearchEvent,identifier)
        account=s.get(PaperAccount,'paper')
        policy=PolicyIn(**get(s,PaperPolicy,account.policy_id).settings) if account else PolicyIn()
        return research.analogues(s,event,policy)

    @app.post('/api/research/import-leads')
    def research_import(s:Session=Depends(session),actor=Depends(writer),core=Depends(core)):
        return research.import_leads(s,actor,core)

    @app.get('/market-chart',include_in_schema=False)
    def market_chart(symbol:str=Query('NYSE:AA',min_length=1,max_length=80,pattern=r'^[A-Z0-9_:./-]+$'),
                     interval:str=Query('D',pattern=r'^(15|60|D|W)$'),
                     theme:str=Query('light',pattern=r'^(light|dark)$')):
        from urllib.parse import quote
        config={'autosize':True,'width':'100%','height':'100%','symbol':symbol,'interval':interval,
                'timezone':'Etc/UTC','theme':theme,'style':'1','locale':'en','allow_symbol_change':False,
                'hide_side_toolbar':False,'calendar':False,'support_host':'https://www.tradingview.com',
                'utm_source':'muniquant','utm_medium':'widget_new','utm_campaign':'advanced-chart'}
        url='https://www.tradingview-widget.com/embed-widget/advanced-chart/?locale=en#'+quote(json.dumps(config))
        return RedirectResponse(url,status_code=307,headers={'Referrer-Policy':'no-referrer','Cache-Control':'no-store'})

    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    @app.get('/',include_in_schema=False)
    def index(): return FileResponse(STATIC/'index.html')
    return app

app=create_app()
