import csv
import io
import json
import logging
import os
import secrets
import hashlib
import time
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from jsonschema import validate
from .db import make_engine, DATABASE_URL
from .models import Entity, Source, Document, Observation, MarketObservation, Relationship, Review, Run, Audit, now
from .schemas import EntityIn, SourceIn, DocumentIn, ObservationIn, RelationshipIn, ResolveIn, DecisionIn, CsvIn
from .services import record, acquire, add_observation, resolve, export_package

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('muniquant')
STATIC=Path(__file__).parent/'static'

def create_app(database_url=None, storage=None, write_token=None):
    Path('data').mkdir(exist_ok=True)
    app=FastAPI(title='MuniQuant Evidence Platform', version='1.0.0')
    app.state.engine=make_engine(database_url or DATABASE_URL)
    app.state.storage=Path(storage or os.getenv('SNAPSHOT_DIR','data/snapshots'))
    app.state.write_token=write_token if write_token is not None else os.getenv('WRITE_TOKEN','')
    app.state.actor=os.getenv('WRITE_ACTOR','local-curator')
    app.state.require_read_auth=os.getenv('REQUIRE_READ_AUTH','false').lower()=='true'
    app.state.read_token=os.getenv('READ_TOKEN','')


    def session():
        with Session(app.state.engine) as s:
            yield s

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
    def create_case(data:CaseIn,s:Session=Depends(session),actor=Depends(writer)):
        c=investigations.create(s,data,actor);audit(s,actor,'investigation_created',c);s.commit();return record(c)

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
    def revise_case(identifier:str,data:RevisionIn,s:Session=Depends(session),actor=Depends(writer)):
        c=investigations.revise(s,get(s,Investigation,identifier),data,actor)
        audit(s,actor,'investigation_revised',c);s.commit();return record(c)

    from .asset_map import LocationIn, DependencyIn, AssetLocation, AssetDependency
    from . import asset_map
    from datetime import date

    @app.get('/api/asset-map')
    def asset_graph(product:str|None=Query(None,pattern='^(bauxite|alumina|primary_aluminium|electricity|other)$'),as_of:date|None=None,s:Session=Depends(session)):
        return asset_map.graph(s,product,as_of)

    @app.post('/api/asset-map/locations',status_code=201)
    def asset_location(data:LocationIn,s:Session=Depends(session),actor=Depends(writer)):
        values=data.model_dump();asset_map.validate_references(s,values)
        obj=AssetLocation(**values,actor=actor);s.add(obj);audit(s,actor,'asset_location',obj);s.commit();return record(obj)

    @app.post('/api/asset-map/dependencies',status_code=201)
    def asset_dependency(data:DependencyIn,s:Session=Depends(session),actor=Depends(writer)):
        values=data.model_dump(mode='json');asset_map.validate_references(s,values)
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
    def chat(data:chatbot.ChatIn,request:Request,s:Session=Depends(session)):
        if data.use_ai:
            writer(request)  # Paid provider access requires an attributable workspace identity.
            if not chatbot.ai_enabled():
                raise HTTPException(503,'AI summaries are not configured; use local mode')
        return chatbot.answer(s,data)

    @app.post('/api/chat/stream')
    def chat_stream(data:chatbot.ChatIn,request:Request,s:Session=Depends(session)):
        if data.use_ai:
            writer(request)
            if not chatbot.ai_enabled():
                raise HTTPException(503,'AI summaries are not configured; use local mode')
        scope, sources = chatbot.retrieve(s,data)
        return StreamingResponse(chatbot.stream_answer(data,scope,sources), media_type='text/event-stream',
            headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

    @app.get('/api/health')
    def health(s:Session=Depends(session)):
        s.execute(text('SELECT 1'))
        import muniquant_core
        return {'status':'ok','native_core':muniquant_core.version,'version':'1.0.0','scope':'upstream-industrial-evidence'}

    @app.get('/api/workspace')
    def workspace(s:Session=Depends(session)):
        models={'entities':Entity,'sources':Source,'documents':Document,'observations':Observation,
                'relationships':Relationship,'reviews':Review,'runs':Run,'audit':Audit}
        from .models import Candidate,EvidenceBuild,RetrievalAttempt
        models.update({'candidates':Candidate,'builds':EvidenceBuild,'retrieval_attempts':RetrievalAttempt})
        result={name:[record(o) for o in s.scalars(select(model).order_by(model.id).limit(1000)).all()] for name,model in models.items()}
        from .models import ObservationDetail
        details={detail.observation_id:detail for detail in s.scalars(select(ObservationDetail))}
        for observation in result['observations']:
            detail=details.get(observation['id'])
            observation['exact_normalized_value']=str(detail.normalized_value) if detail and detail.normalized_value is not None else None
        result['workspace_limit']=1000
        return result

    @app.get('/api/records/{record_type}')
    def records(record_type:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=1000),s:Session=Depends(session)):
        from sqlalchemy import func
        from .models import Candidate,EvidenceBuild,RetrievalAttempt,SourceAccess,Lead,LeadRevision,LeadHeadline
        models={'entities':Entity,'sources':Source,'documents':Document,'observations':Observation,'relationships':Relationship,'reviews':Review,'runs':Run,'audit':Audit,'candidates':Candidate,'builds':EvidenceBuild,'retrieval_attempts':RetrievalAttempt,'source_access':SourceAccess,'leads':Lead,'lead_revisions':LeadRevision,'lead_headlines':LeadHeadline}
        model=models.get(record_type)
        if model is None: raise HTTPException(404,'Unknown record type')
        return {'records':[record(o) for o in s.scalars(select(model).order_by(model.id).offset(offset).limit(limit))],'total':s.scalar(select(func.count()).select_from(model)),'offset':offset,'limit':limit}

    @app.post('/api/entities',status_code=201)
    def entity(data:EntityIn, s:Session=Depends(session), actor=Depends(writer)):
        obj=Entity(**data.model_dump()); s.add(obj); s.flush();
        from .domain import sync_entity
        sync_entity(s,obj,actor); audit(s,actor,'create',obj); s.commit(); return record(obj)

    @app.post('/api/sources',status_code=201)
    def source(data:SourceIn, s:Session=Depends(session), actor=Depends(writer)):
        obj=Source(**data.model_dump()); s.add(obj); audit(s,actor,'create',obj); s.commit(); return record(obj)

    @app.post('/api/documents',status_code=201)
    def document(data:DocumentIn, s:Session=Depends(session), actor=Depends(writer)):
        try: obj,duplicate=acquire(s,app.state.storage,data)
        except ValueError as exc:
            s.rollback(); s.add(Run(status='failed',manifest={'source_id':data.source_id,'adapter':'text-upload-v1','error':str(exc)})); s.commit(); raise
        audit(s,actor,'duplicate' if duplicate else 'acquire',obj); s.commit()
        return dict(record(obj),duplicate=duplicate)

    @app.get('/api/documents/{identifier}/content')
    def content(identifier:str,s:Session=Depends(session)):
        import hashlib
        doc=get(s,Document,identifier); path=app.state.storage/doc.content_hash
        if not path.exists(): raise HTTPException(409,'Snapshot missing')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=doc.content_hash: raise HTTPException(409,'Snapshot integrity failure')
        return Response(raw,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{doc.content_hash}.txt"'})

    @app.post('/api/observations',status_code=201)
    def observation(data:ObservationIn,s:Session=Depends(session),actor=Depends(writer)):
        obj=add_observation(s,data); audit(s,actor,'observe',obj); s.commit(); return record(obj)

    @app.post('/api/relationships',status_code=201)
    def relationship(data:RelationshipIn,s:Session=Depends(session),actor=Depends(writer)):
        if get(s,Entity,data.company_id).kind!='company' or get(s,Entity,data.facility_id).kind!='facility':
            raise ValueError('Relationship requires a company and a facility')
        from .services import require_citable
        require_citable(s,get(s,Document,data.document_id))
        obj=Relationship(**data.model_dump(mode='json',exclude={'evidence_reference'})); s.add(obj); s.flush()
        from .models import CompanyFacilityRelationship
        from decimal import Decimal
        s.add(CompanyFacilityRelationship(relationship_id=obj.id,company_id=data.company_id,facility_id=data.facility_id,document_id=data.document_id,role=data.role,evidence_reference=data.evidence_reference,percentage=Decimal(str(data.percentage)) if data.percentage is not None else None,valid_from=data.valid_from,valid_to=data.valid_to))
        audit(s,actor,'relate',obj); s.commit(); return record(obj)

    @app.post('/api/resolve')
    def resolver(data:ResolveIn,s:Session=Depends(session),actor=Depends(writer)):
        result=resolve(s,data.name,data.country,data.entity_kind)
        if result['status']!='resolved':
            obj=Review(raw_name=data.name,candidate_ids=[e['id'] for e in result['candidates']]);s.add(obj)
            audit(s,actor,'queue_review',obj);s.commit();result['review_id']=obj.id
        return result

    from .schemas import ReviewCandidateIn
    @app.post('/api/reviews/{identifier}/candidates',status_code=201)
    def review_candidate(identifier:str,data:ReviewCandidateIn,s:Session=Depends(session),actor=Depends(writer)):
        obj=s.scalar(select(Review).where(Review.id==identifier).with_for_update())
        if not obj: raise HTTPException(404,'Review not found')
        if obj.status!='pending': raise HTTPException(409,'Review already decided')
        selected=get(s,Entity,data.entity_id)
        from .models import Candidate
        extracted=s.scalar(select(Candidate).where(Candidate.review_id==identifier))
        if extracted and (selected.kind!='facility' or (extracted.country and selected.country!=extracted.country)):
            raise ValueError('Extracted facility candidate must match the reported country and kind')
        obj.candidate_ids=sorted(set([*obj.candidate_ids,selected.id]))
        s.add(Audit(actor=actor,action='review_candidate',record_id=identifier,detail=data.model_dump()));s.commit();return record(obj)

    @app.post('/api/reviews/{identifier}/decision')
    def decision(identifier:str,data:DecisionIn,s:Session=Depends(session),actor=Depends(writer)):
        # Serialize decisions on PostgreSQL; conditional UPDATE also protects SQLite.
        from sqlalchemy import update
        obj=get(s,Review,identifier)
        if data.selected_entity_id is not None and data.selected_entity_id not in obj.candidate_ids:
            raise ValueError('Selection must be one of the recorded candidates')
        updated=s.execute(update(Review).where(Review.id==identifier,Review.status=='pending').values(
            status='accepted' if data.selected_entity_id else 'rejected',selected_entity_id=data.selected_entity_id,
            reviewer=actor,reason=data.reason,decided_at=now()))
        if updated.rowcount!=1: raise HTTPException(409,'Review already decided')
        s.refresh(obj)
        from .pipeline import apply_review
        apply_review(s,obj,actor)
        audit(s,actor,'review_decision',obj);s.commit();s.refresh(obj);return record(obj)

    @app.post('/api/import/csv')
    def import_csv(data:CsvIn,s:Session=Depends(session),actor=Depends(writer)):
        from .pipeline import extract
        from .schemas import ExtractionIn
        from .models import Candidate
        doc=get(s,Document,data.document_id)
        # Stable sentinel default: CSV provides its own actual dates in each row.
        build,duplicate=extract(s,app.state.storage,doc.id,ExtractionIn(adapter='csv-v1',valid_from='1970-01-01'),actor)
        s.commit()
        candidates=s.scalars(select(Candidate).where(Candidate.build_id==build.id)).all()
        return {'inserted':0 if duplicate else sum(c.observation_id is not None for c in candidates),'ids':[c.observation_id for c in candidates if c.observation_id],'duplicate':duplicate,'build_id':build.id,'pending_review':sum(c.status!='resolved' for c in candidates)}

    @app.get('/api/export/draft')
    def export(s:Session=Depends(session)):
        package=export_package(s,app.state.storage)
        validate(package,json.loads((Path(__file__).parent/'package.schema.json').read_text()))
        return JSONResponse(package,headers={'Content-Disposition':'attachment; filename="commodity-evidence-package.json"'})


    from .schemas import SourceAccessIn,RetrievalIn,ExtractionIn,AliasIn,SupersessionIn
    from .models import SourceAccess,Country,FacilityType,Commodity,Candidate,EvidenceBuild

    @app.get('/api/reference-data')
    def references(s:Session=Depends(session)):
        return {name:[record(o) for o in s.scalars(select(model).order_by(model.code))] for name,model in {'countries':Country,'facility_types':FacilityType,'commodities':Commodity}.items()}

    from .schemas import EntityEvidenceIn
    from .models import EntityEvidence
    @app.post('/api/entities/{identifier}/evidence',status_code=201)
    def identity_evidence(identifier:str,data:EntityEvidenceIn,s:Session=Depends(session),actor=Depends(writer)):
        from .services import require_citable
        get(s,Entity,identifier);require_citable(s,get(s,Document,data.document_id))
        key=(identifier,data.document_id)
        if s.get(EntityEvidence,key): raise HTTPException(409,'Identity evidence already registered')
        obj=EntityEvidence(entity_id=identifier,**data.model_dump(),reviewer=actor);s.add(obj)
        s.add(Audit(actor=actor,action='identity_evidence',record_id=identifier,detail=data.model_dump()));s.commit();return record(obj)

    @app.post('/api/entities/{identifier}/aliases',status_code=201)
    def alias(identifier:str,data:AliasIn,s:Session=Depends(session),actor=Depends(writer)):
        from .domain import add_alias
        obj=add_alias(s,identifier,data.name,actor,data.reason);audit(s,actor,'alias',obj);s.commit();return record(obj)

    @app.post('/api/entities/{identifier}/supersession',status_code=201)
    def supersession(identifier:str,data:SupersessionIn,s:Session=Depends(session),actor=Depends(writer)):
        from .domain import supersede
        obj=supersede(s,identifier,data.new_entity_id,actor,data.reason)
        s.add(Audit(actor=actor,action='supersede',record_id=identifier,detail={'new_entity_id':data.new_entity_id,'reason':data.reason}));s.commit();return record(obj)

    @app.post('/api/sources/{identifier}/access',status_code=201)
    def access(identifier:str,data:SourceAccessIn,s:Session=Depends(session),actor=Depends(writer)):
        source=get(s,Source,identifier)
        values=data.model_dump()
        previous=s.scalar(select(SourceAccess).where(SourceAccess.source_id==identifier).order_by(SourceAccess.decided_at.desc(),SourceAccess.id.desc()))
        # A re-review that omits usage or credential fields keeps them; dropping them needs an explicit value.
        if previous and 'usage_scope' not in data.model_fields_set: values['usage_scope']=previous.usage_scope
        if previous and 'credential_ref' not in data.model_fields_set and 'auth_header' not in data.model_fields_set:
            values['credential_ref'],values['auth_header']=previous.credential_ref,previous.auth_header
        from .acquisition import check_credential_binding
        check_credential_binding(values['credential_ref'],values['allowed_hosts'])
        obj=SourceAccess(source_id=identifier,**values,reviewer=actor);s.add(obj);source.access_status=data.status
        audit(s,actor,'access_decision',obj);s.commit();return record(obj)

    @app.post('/api/acquire',status_code=201)
    def remote(data:RetrievalIn,s:Session=Depends(session),actor=Depends(writer)):
        from .acquisition import acquire_remote
        obj,duplicate,run_id=acquire_remote(s,app.state.storage,data,actor)
        audit(s,actor,'remote_acquire',obj);s.commit();return dict(record(obj),duplicate=duplicate,run_id=run_id)

    @app.post('/api/documents/{identifier}/extract',status_code=201)
    def extraction(identifier:str,data:ExtractionIn,s:Session=Depends(session),actor=Depends(writer)):
        from .pipeline import extract
        build,duplicate=extract(s,app.state.storage,identifier,data,actor);s.commit()
        return {'build':record(build),'duplicate':duplicate,'candidates':[record(c) for c in s.scalars(select(Candidate).where(Candidate.build_id==build.id))]}

    @app.post('/api/builds/{identifier}/replay')
    def replay_build(identifier:str,s:Session=Depends(session),actor=Depends(writer)):
        from .pipeline import replay
        return replay(s,app.state.storage,identifier)

    @app.get('/api/quality')
    def quality(s:Session=Depends(session)):
        from .quality import inspect_quality
        return inspect_quality(s,app.state.storage)

    @app.get('/api/export')
    def export_contract(s:Session=Depends(session)):
        from .contract import export_v1
        return JSONResponse(export_v1(s,app.state.storage),headers={'Content-Disposition':'attachment; filename="commodity-evidence-package-v1.json"'})

    @app.get('/api/export/schema')
    def contract_schema():
        return FileResponse(Path(__file__).parent/'evidence-v1.schema.json',media_type='application/schema+json')

    # Licensed Permutable feed: lead-only, factual events/headlines, never exported as evidence.
    from .schemas import PermutableSourceIn,PermutableCaptureIn,LeadDecisionIn
    from . import permutable

    @app.post('/api/permutable/source',status_code=201)
    def permutable_source(data:PermutableSourceIn,s:Session=Depends(session),actor=Depends(writer)):
        source,policy=permutable.register_source(s,actor,data)
        return {'source':record(source),'access':record(policy)}

    @app.post('/api/permutable/capture')
    def permutable_capture(data:PermutableCaptureIn,s:Session=Depends(session),actor=Depends(writer)):
        result=permutable.capture(s,app.state.storage,actor,data)
        if data.feed in ('events','event_headlines'):
            try:
                result['research_bridge']=research.import_leads(s,actor,result['document_ids'],live=data.mode=='live')
            except (ValueError,LookupError) as exc:
                s.rollback()
                result['research_bridge']={'status':'blocked','reason':str(exc)}
        return result

    @app.post('/api/permutable/documents/{identifier}/replay')
    def permutable_replay(identifier:str,s:Session=Depends(session),actor=Depends(writer)):
        return permutable.replay_document(s,app.state.storage,identifier)

    @app.get('/api/leads')
    def leads(status:str|None=Query(None,pattern='^(new|follow_up|dismissed|confirmed)$'),topic:str|None=Query(None,max_length=200),matched:bool|None=None,search:str|None=Query(None,max_length=500),
              offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),s:Session=Depends(session)):
        return {**permutable.list_leads(s,status,offset,limit,topic,matched,search),'source_id':permutable.SOURCE_ID}

    @app.post('/api/leads/{identifier}/decision')
    def lead_decision(identifier:str,data:LeadDecisionIn,s:Session=Depends(session),actor=Depends(writer)):
        try: return record(permutable.decide(s,identifier,data,actor))
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
    def research_event(data:EventIn,s:Session=Depends(session),actor=Depends(writer)):
        try: return research.ingest_event(s,data,actor)
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
    def research_import(s:Session=Depends(session),actor=Depends(writer)):
        return research.import_leads(s,actor)

    @app.get('/market-chart',include_in_schema=False)
    def market_chart(symbol:str=Query('NYSE:AA',min_length=1,max_length=80,pattern=r'^[A-Z0-9_:./-]+$'),
                     interval:str=Query('D',pattern=r'^(15|60|D|W)$')):
        from urllib.parse import quote
        config={'autosize':True,'width':'100%','height':'100%','symbol':symbol,'interval':interval,
                'timezone':'Etc/UTC','theme':'dark','style':'1','locale':'en','allow_symbol_change':False,
                'hide_side_toolbar':False,'calendar':False,'support_host':'https://www.tradingview.com',
                'utm_source':'muniquant','utm_medium':'widget_new','utm_campaign':'advanced-chart'}
        url='https://www.tradingview-widget.com/embed-widget/advanced-chart/?locale=en#'+quote(json.dumps(config))
        return RedirectResponse(url,status_code=307,headers={'Referrer-Policy':'no-referrer','Cache-Control':'no-store'})

    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    @app.get('/',include_in_schema=False)
    def index(): return FileResponse(STATIC/'index.html')
    return app

app=create_app()
