import csv
import io
import json
import logging
import os
import secrets
import time
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from jsonschema import validate
from .db import make_engine, DATABASE_URL
from .models import (
    Entity, Source, Document, Observation, MarketObservation, Relationship, Review, Run, Audit, now,
    QualityCheckResult, QualityRun, ResolutionMatch, RetrievalAttempt, SourceAccess,
)
from .schemas import EntityIn, SourceIn, DocumentIn, ObservationIn, MarketIn, RelationshipIn, ResolveIn, DecisionIn, CsvIn, SourceAccessIn
from .services import record, acquire, add_observation, resolve, export_package, canonical
from .export_v1 import iter_cep_v1
from .quality import run_quality
from .trace import trace_observation

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('muniquant')
STATIC=Path(__file__).parent/'static'

def create_app(database_url=None, storage=None, write_token=None):
    Path('data').mkdir(exist_ok=True)
    app=FastAPI(title='MuniQuant Evidence Platform', version='0.1.0')
    app.state.engine=make_engine(database_url or DATABASE_URL)
    app.state.storage=Path(storage or os.getenv('SNAPSHOT_DIR','data/snapshots'))
    app.state.write_token=write_token if write_token is not None else os.getenv('WRITE_TOKEN','')
    app.state.actor=os.getenv('WRITE_ACTOR','local-curator')

    def session():
        with Session(app.state.engine) as s:
            yield s

    def writer(request:Request):
        token=request.headers.get('authorization','').removeprefix('Bearer ')
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
        # Guard both declared and streamed bodies before JSON parsing.
        if request.method in ('POST','PUT','PATCH'):
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>2_500_000: return JSONResponse({'detail':'Request exceeds 2.5 MB'},status_code=413)
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
        return {'status':'ok','native_core':muniquant_core.version,'version':'0.1.0'}

    @app.get('/api/workspace')
    def workspace(s:Session=Depends(session)):
        models={'entities':Entity,'sources':Source,'documents':Document,'observations':Observation,
                'market':MarketObservation,'relationships':Relationship,'reviews':Review,'runs':Run,'audit':Audit,
                'source_access':SourceAccess,'retrieval_attempts':RetrievalAttempt,'resolution_matches':ResolutionMatch,
                'quality_runs':QualityRun,'quality_results':QualityCheckResult}
        result={}
        for name,model in models.items():
            # ResolutionMatch has a composite key and intentionally no synthetic id.
            order_by=tuple(model.__table__.primary_key.columns)
            result[name]=[record(o) for o in s.scalars(select(model).order_by(*order_by)).all()]
        return result

    @app.post('/api/entities',status_code=201)
    def entity(data:EntityIn, s:Session=Depends(session), actor=Depends(writer)):
        obj=Entity(**data.model_dump()); s.add(obj); audit(s,actor,'create',obj); s.commit(); return record(obj)

    @app.post('/api/sources',status_code=201)
    def source(data:SourceIn, s:Session=Depends(session), actor=Depends(writer)):
        obj=Source(**data.model_dump()); s.add(obj); audit(s,actor,'create',obj); s.commit(); return record(obj)

    @app.post('/api/source-access',status_code=201)
    def source_access(data:SourceAccessIn,s:Session=Depends(session),actor=Depends(writer)):
        get(s,Source,data.source_id)
        obj=SourceAccess(**data.model_dump());s.add(obj);audit(s,actor,'source_access',obj);s.commit();return record(obj)

    @app.post('/api/documents',status_code=201)
    def document(data:DocumentIn, s:Session=Depends(session), actor=Depends(writer)):
        try: obj,duplicate=acquire(s,app.state.storage,data)
        except ValueError as exc:
            s.rollback()
            run=Run(status='failed',finished_at=now(),manifest={'source_id':data.source_id,'adapter':'text-upload-v1','adapter_version':'1.0.0','error':str(exc)})
            s.add(run);s.flush()
            if s.get(Source,data.source_id):
                s.add(RetrievalAttempt(run_id=run.id,source_id=data.source_id,requested_url=data.original_url,
                                       outcome='FAILED',error_message=str(exc)))
            s.commit(); raise
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
        obj=Relationship(**data.model_dump(mode='json')); s.add(obj); audit(s,actor,'relate',obj); s.commit(); return record(obj)

    @app.post('/api/market',status_code=201)
    def market(data:MarketIn,s:Session=Depends(session),actor=Depends(writer)):
        doc=get(s,Document,data.document_id)
        source=get(s,Source,doc.source_id)
        if source.source_type=='synthetic' and data.data_status!='synthetic': raise ValueError('Synthetic evidence must remain labelled synthetic')
        obj=MarketObservation(**data.model_dump(mode='json')); s.add(obj); audit(s,actor,'market_observation',obj); s.commit(); return record(obj)

    @app.post('/api/resolve')
    def resolver(data:ResolveIn,s:Session=Depends(session),actor=Depends(writer)):
        result=resolve(s,data.name,data.country)
        if result['status']!='resolved':
            obj=Review(raw_name=data.name,normalized_name=canonical(data.name),match_method=result['match_method'],
                       context={'country':data.country} if data.country else {},
                       candidate_ids=[e['id'] for e in result['candidates']]);s.add(obj);s.flush()
            for match in result['matches']:
                s.add(ResolutionMatch(review_id=obj.id,**match))
            audit(s,actor,'queue_review',obj);s.commit();result['review_id']=obj.id
        return result

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
        audit(s,actor,'review_decision',obj);s.commit();s.refresh(obj);return record(obj)

    @app.post('/api/import/csv')
    def import_csv(data:CsvIn,s:Session=Depends(session),actor=Depends(writer)):
        doc=get(s,Document,data.document_id)
        if doc.media_type!='text/csv': raise ValueError('Register CSV evidence first')
        import hashlib
        raw=(app.state.storage/doc.content_hash).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=doc.content_hash: raise ValueError('Snapshot integrity failure')
        for previous in s.scalars(select(Run).where(Run.status=='success')):
            if previous.manifest.get('adapter')=='capacity-csv-v1' and previous.manifest.get('document_id')==doc.id:
                return {'inserted':0,'ids':previous.manifest['observation_ids'],'duplicate':True}
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        required={'facility_name','country','reported_value','reported_unit','valid_from','evidence_reference'}
        if not required.issubset(reader.fieldnames or []): raise ValueError('Required CSV columns: '+', '.join(sorted(required)))
        inserted=[]
        try:
            for number,row in enumerate(reader,2):
                if number>1002: raise ValueError('CSV limit is 1000 records')
                match=resolve(s,row['facility_name'],row['country'])
                if match['status']!='resolved': raise ValueError(f'Row {number}: unresolved or ambiguous facility; use the review workflow')
                obs=add_observation(s,ObservationIn(entity_id=match['entity_id'],document_id=doc.id,
                    reported_value=row['reported_value'],reported_unit=row['reported_unit'],valid_from=row['valid_from'],evidence_reference=row['evidence_reference']))
                obs.parser_version='capacity-csv-v1'
                audit(s,actor,'csv_observe',obs);inserted.append(obs.id)
        except Exception:
            s.rollback(); raise
        s.add(Run(status='success',manifest={'adapter':'capacity-csv-v1','document_id':doc.id,'content_hash':doc.content_hash,'observation_ids':inserted}))
        s.commit();return {'inserted':len(inserted),'ids':inserted}

    @app.get('/api/export')
    def export(s:Session=Depends(session)):
        package=export_package(s,app.state.storage)
        validate(package,json.loads((Path(__file__).parent/'package.schema.json').read_text()))
        return JSONResponse(package,headers={'Content-Disposition':'attachment; filename="commodity-evidence-package.json"'})

    @app.get('/api/observations/{identifier}/trace')
    def observation_trace(identifier:str,s:Session=Depends(session)):
        try: return trace_observation(s,app.state.storage,identifier)
        except LookupError as exc: raise HTTPException(404,str(exc))

    @app.post('/api/quality/runs',status_code=201)
    def quality_run(s:Session=Depends(session),actor=Depends(writer)):
        run,findings=run_quality(s);audit(s,actor,'quality_run',run);s.commit()
        return {'run':record(run),'findings':[record(item) for item in findings]}

    @app.get('/api/quality/latest')
    def quality_latest(s:Session=Depends(session)):
        run=s.scalar(select(QualityRun).order_by(QualityRun.started_at.desc()).limit(1))
        if not run:return {'run':None,'findings':[]}
        findings=s.scalars(select(QualityCheckResult).where(QualityCheckResult.quality_run_id==run.id)
                           .order_by(QualityCheckResult.severity.desc(),QualityCheckResult.check_code)).all()
        return {'run':record(run),'findings':[record(item) for item in findings]}

    @app.get('/api/export/cep-v1.jsonl')
    def export_cep_v1(s:Session=Depends(session)):
        # Evaluate while the request-owned session is definitely open. The pilot
        # export is bounded; true streaming can use a separately-owned session once
        # pagination/batch export is introduced.
        lines=[json.dumps(item,separators=(',',':'),ensure_ascii=False)+'\n'
               for item in iter_cep_v1(s,app.state.storage)]
        return StreamingResponse(iter(lines),media_type='application/x-ndjson',
                                 headers={'Content-Disposition':'attachment; filename="commodity-evidence-package-v1.jsonl"'})

    from .trading import register_routes
    register_routes(app,session,writer)

    app.mount('/static',StaticFiles(directory=STATIC),name='static')
    @app.get('/',include_in_schema=False)
    def index(): return FileResponse(STATIC/'index.html')
    return app

app=create_app()
