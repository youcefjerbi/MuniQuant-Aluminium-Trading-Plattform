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
from fastapi.responses import FileResponse, JSONResponse, Response
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
        if app.state.require_read_auth and request.method=='GET' and request.url.path.startswith('/api/') and request.url.path!='/api/health':
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
        response.headers['Referrer-Policy']='same-origin'
        if request.url.path in ('/','/static/app.js','/static/style.css'):
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        logger.info(json.dumps({'method':request.method,'path':request.url.path,'status':response.status_code,'duration_ms':round((time.monotonic()-start)*1000)}))
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc): return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc): return JSONResponse({'detail':'Conflicting record or invalid reference; refresh and retry'},status_code=409)

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
        from .models import Candidate,EvidenceBuild,RetrievalAttempt,SourceAccess
        models={'entities':Entity,'sources':Source,'documents':Document,'observations':Observation,'relationships':Relationship,'reviews':Review,'runs':Run,'audit':Audit,'candidates':Candidate,'builds':EvidenceBuild,'retrieval_attempts':RetrievalAttempt,'source_access':SourceAccess}
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
        get(s,Document,data.document_id)
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
        get(s,Entity,identifier);get(s,Document,data.document_id)
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
        obj=SourceAccess(source_id=identifier,**data.model_dump(),reviewer=actor);s.add(obj);source.access_status=data.status
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

    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    @app.get('/',include_in_schema=False)
    def index(): return FileResponse(STATIC/'index.html')
    return app

app=create_app()
