"""Content fingerprints and verified reads of preserved lead-feed responses."""
import hashlib
import json
from pathlib import Path

def logical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def snapshot_bytes(storage,doc):
    path=Path(storage)/doc.content_hash
    if not path.is_file(): raise ValueError('Snapshot is missing')
    if path.stat().st_size>10_000_000: raise ValueError('Snapshot exceeds 10 MB limit')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=doc.content_hash: raise ValueError('Snapshot integrity failure')
    return raw
