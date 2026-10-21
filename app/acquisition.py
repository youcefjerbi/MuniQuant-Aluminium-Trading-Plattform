"""Capture of licensed lead feeds into the Workspace's lead store.

Explicit permitted URLs only: public-IP-pinned HTTPS, bounded snapshots and attempt logs.
"""
import hashlib
import http.client
import ipaddress
import os
import random
import socket
import ssl
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from sqlalchemy import select, func
from .models import LeadSource as Source, LeadSourceAccess as SourceAccess, LeadSnapshot as SourceSnapshot, LeadDocumentVersion as DocumentVersion, LeadSourceDocument as SourceDocumentRelation, LeadDocument as Document, LeadRun as Run, LeadRetrievalAttempt as RetrievalAttempt

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

def licensed_credentials():
    """Server-side binding of credential variable names to the only hosts allowed to receive them.

    Without this binding a writer could name any server secret (WRITE_TOKEN, DATABASE_URL...) as a
    credential and send it to a host they approve. Override with LICENSED_CREDENTIALS_JSON."""
    import json
    raw=os.getenv('LICENSED_CREDENTIALS_JSON')
    bindings=json.loads(raw) if raw else {'PERMUTABLE_API_KEY':['copilot-api.permutable.ai']}
    if not isinstance(bindings,dict) or any(not isinstance(h,list) or not all(isinstance(x,str) for x in h) for h in bindings.values()):
        raise ValueError('LICENSED_CREDENTIALS_JSON must map credential names to host lists')
    return {name:{h.lower() for h in hosts} for name,hosts in bindings.items()}

def check_credential_binding(credential_ref,allowed_hosts):
    if not credential_ref: return
    bound=licensed_credentials().get(credential_ref)
    if bound is None: raise ValueError('Credential '+credential_ref+' is not a registered licensed credential on this server')
    if not allowed_hosts or not set(allowed_hosts)<=bound: raise ValueError('Credential '+credential_ref+' may only be sent to its registered hosts')

def credential_headers(policy):
    """Resolve a licensed API credential from the server environment; only its variable name is stored."""
    if not policy.credential_ref: return {}
    check_credential_binding(policy.credential_ref,policy.allowed_hosts)
    value=os.environ.get(policy.credential_ref,'').strip()
    if not value: raise ValueError('Credential '+policy.credential_ref+' is not configured on this server')
    # Reject control/space characters up front so header errors can never echo the secret.
    if any(not 33<=ord(c)<=126 for c in value): raise ValueError('Credential '+policy.credential_ref+' contains invalid characters')
    return {policy.auth_header:value}

def redact(message,headers):
    for secret in (headers or {}).values():
        if secret: message=message.replace(secret,'[redacted]')
    return message

def fetch_once(url, allowed_hosts, headers=None):
    for hop in range(4):
        host,address,parts=public_target(url,allowed_hosts)
        connection=PinnedHTTPS(host,address)
        try:
            path=parts.path or '/'
            if parts.query: path+='?'+parts.query
            connection.request('GET',path,headers={'User-Agent':'MuniQuantEvidence/1.0 (bounded industrial research capture)', 'Accept-Encoding':'identity', **(headers or {})})
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

def acquire_remote(s,storage,data,actor,fetch=fetch_once,adapter='https-v1'):
    run=Run(status='running',pipeline_version='1.0.0',manifest={'source_id':data.source_id,'url':data.url,'adapter':adapter,'actor':actor})
    # Commit before any network wait: an open write transaction would lock SQLite for the whole download.
    s.add(run);s.commit()
    headers={}
    try:
        source=s.get(Source,data.source_id)
        policy=s.scalar(select(SourceAccess).where(SourceAccess.source_id==data.source_id).order_by(SourceAccess.decided_at.desc(),SourceAccess.id.desc()))
        if not source or not policy or source.access_status!='permitted' or policy.status!='permitted' or not policy.allowed_hosts:
            raise ValueError('An audited permitted source-access policy with approved hosts is required')
        headers=credential_headers(policy)
        if policy.credential_ref: run.manifest={**run.manifest,'credential_ref':policy.credential_ref}
        for attempt in range(1,4):
            status=None
            try:
                # Licensed credentials travel only in headers; URLs, logs and manifests never carry them.
                status,raw,media,final_url=fetch(data.url,policy.allowed_hosts,*([headers] if headers else []))
                if status!=200: raise OSError('HTTP '+str(status))
                s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=attempt,status='success',http_status=status))
                obj,duplicate=register_bytes(s,storage,{'source_id':data.source_id,'title':data.title,'original_url':data.url,'published_at':data.published_at.isoformat() if data.published_at else None,'media_type':media},raw)
                run.status='duplicate' if duplicate else 'success'
                run.manifest={**run.manifest,'document_id':obj.id,'content_hash':obj.content_hash,'final_url':final_url,'access_decision_id':policy.id}
                s.commit();return obj,duplicate,run.id
            except (OSError, http.client.HTTPException) as exc:
                s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=attempt,status='failed',http_status=status,error=redact(str(exc),headers)[:300]))
                if status is not None and status not in (408,429,500,502,503,504): break
                # Rate limits get exponential back-off with jitter (1 s, 2 s), as licensed APIs request.
                if attempt<3: time.sleep(2**(attempt-1)+random.uniform(0,0.25) if status==429 else 0.25*attempt)
        raise ValueError('Retrieval failed; see attempt log')
    except ValueError as exc:
        message=redact(str(exc),headers)
        run.status='failed';run.manifest={**run.manifest,'error':message}
        s.add(RetrievalAttempt(run_id=run.id,url=data.url,attempt=0,status='blocked',error=message[:300]))
        s.commit()
        if message!=str(exc): raise ValueError(message) from None
        raise
