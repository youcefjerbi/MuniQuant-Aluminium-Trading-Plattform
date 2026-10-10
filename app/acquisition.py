"""Explicit permitted URLs only: public-IP-pinned HTTPS, bounded snapshots and attempt logs."""
import hashlib
import http.client
import ipaddress
import os
import socket
import ssl
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from sqlalchemy import select, func
from .models import Source, SourceAccess, SourceSnapshot, DocumentVersion, SourceDocumentRelation, Document, Run, RetrievalAttempt

MAX_BYTES = 10_000_000
MEDIA = {'text/plain', 'text/html', 'text/csv', 'application/pdf', 'application/json'}

def public_target(url, allowed_hosts):
    parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.fragment or parts.port not in (None,443):
        raise ValueError('Acquisition requires an HTTPS URL without credentials, fragment or custom port')
    host=parts.hostname.lower().rstrip('.')
    if host not in allowed_hosts: raise ValueError('Host not approved in source-access policy')
    addresses=sorted({info[4][0] for info in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Source resolves to a non-public network address')
    return host,addresses[0],parts

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host,timeout=20,context=ssl.create_default_context())
        self.address=address
    def connect(self):
        # Pin the checked address; do not resolve the hostname a second time.
        sock=socket.create_connection((self.address,443),timeout=self.timeout)
        self.sock=self._context.wrap_socket(sock,server_hostname=self.host)

def fetch_once(url, allowed_hosts):
    for hop in range(4):
        host,address,parts=public_target(url,allowed_hosts)
        connection=PinnedHTTPS(host,address)
        try:
            path=parts.path or '/'
            if parts.query: path+='?'+parts.query
            connection.request('GET',path,headers={'User-Agent':'MuniQuantEvidence/1.0 (bounded industrial research capture)', 'Accept-Encoding':'identity'})
            response=connection.getresponse()
            status=response.status
            if status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location: raise ValueError('Redirect has no location')
                url=urljoin(url,location)
                continue
            if status!=200: return status,b'',None,url
            media=(response.getheader('Content-Type') or '').split(';')[0].lower()
            if media not in MEDIA: raise ValueError('Unsupported evidence content type: '+media)
            if response.getheader('Content-Encoding') not in (None,'identity'): raise ValueError('Compressed responses are not accepted')
            length=response.getheader('Content-Length')
            if length and int(length)>MAX_BYTES: raise ValueError('Document exceeds 10 MB limit')
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: raise ValueError('Document exceeds 10 MB limit')
            if not raw: raise ValueError('Empty evidence document')
            return status,raw,media,url
        finally: connection.close()
    raise ValueError('Redirect limit exceeded')

def preserve(storage,raw):
    digest=hashlib.sha256(raw).hexdigest()
    root=Path(storage);root.mkdir(parents=True,exist_ok=True)
    path=root/digest
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('Snapshot integrity failure')
        return digest
    # Atomic publication of a complete file; an orphan snapshot after rollback is safe.
    fd,temp=tempfile.mkstemp(dir=root,prefix='.capture-')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        try: os.link(temp,path)
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('Snapshot integrity failure')
    finally: os.unlink(temp)
    return digest

def register_bytes(s,storage,metadata,raw):
    source=s.scalar(select(Source).where(Source.id==metadata['source_id']).with_for_update())
    if not source or source.access_status not in ('permitted','synthetic'): raise ValueError('Source acquisition is not permitted')
    policy=s.scalar(select(SourceAccess).where(SourceAccess.source_id==source.id).order_by(SourceAccess.decided_at.desc(),SourceAccess.id.desc()))
    if policy and policy.status!='permitted': raise ValueError('Current source-access decision blocks capture')
    if not raw or len(raw)>MAX_BYTES: raise ValueError('Invalid snapshot size')
    digest=preserve(storage,raw)
    snapshot=s.get(SourceSnapshot,digest)
    if not snapshot: s.add(SourceSnapshot(content_hash=digest,storage_reference=digest,byte_size=len(raw)));s.flush()
    elif snapshot.byte_size is None: snapshot.byte_size=len(raw)
    existing=s.scalar(select(Document).where(Document.source_id==source.id,Document.original_url==metadata['original_url'],Document.content_hash==digest))
    if existing: return existing,True
    version=(s.scalar(select(func.max(Document.version)).where(Document.source_id==source.id,Document.original_url==metadata['original_url'])) or 0)+1
    obj=Document(**metadata,content_hash=digest,version=version);s.add(obj);s.flush()
    s.add(DocumentVersion(document_id=obj.id,snapshot_hash=digest,version=version))
    s.add(SourceDocumentRelation(source_id=source.id,document_id=obj.id));s.flush()
    return obj,False

def acquire_remote(s,storage,data,actor,fetch=fetch_once):
    run=Run(status='running',pipeline_version='1.0.0',manifest={'source_id':data.source_id,'url':data.url,'adapter':'https-v1','actor':actor})
    s.add(run);s.flush()
    try:
        source=s.get(Source,data.source_id)
        policy=s.scalar(select(SourceAccess).where(SourceAccess.source_id==data.source_id).order_by(SourceAccess.decided_at.desc(),SourceAccess.id.desc()))
        if not source or not policy or source.access_status!='permitted' or policy.status!='permitted' or not policy.allowed_hosts:
            raise ValueError('An audited permitted source-access policy with approved hosts is required')
        for attempt in range(1,4):
            status=None
            try:
                status,raw,media,final_url=fetch(data.url,policy.allowed_hosts)
                if status!=200: raise OSError('HTTP '+str(status))
                s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=attempt,status='success',http_status=status))
                obj,duplicate=register_bytes(s,storage,{'source_id':data.source_id,'title':data.title,'original_url':data.url,'published_at':data.published_at.isoformat() if data.published_at else None,'media_type':media},raw)
                run.status='duplicate' if duplicate else 'success'
                run.manifest={**run.manifest,'document_id':obj.id,'content_hash':obj.content_hash,'final_url':final_url,'access_decision_id':policy.id}
                s.commit();return obj,duplicate,run.id
            except (OSError, http.client.HTTPException) as exc:
                s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=attempt,status='failed',http_status=status,error=str(exc)[:300]))
                if status is not None and status not in (408,429,500,502,503,504): break
                if attempt<3: time.sleep(0.25*attempt)
        raise ValueError('Retrieval failed; see attempt log')
    except ValueError as exc:
        run.status='failed';run.manifest={**run.manifest,'error':str(exc)}
        s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=0,status='blocked',error=str(exc)[:300]))
        s.commit();raise
