"""Observation-to-evidence trace construction with snapshot verification."""
import hashlib
from pathlib import Path
from sqlalchemy.orm import Session

from .models import Document, Entity, Observation, Run, Source
from .services import record


def trace_observation(session: Session, storage: Path, observation_id: str):
    observation = session.get(Observation, observation_id)
    if not observation:
        raise LookupError("Observation not found")
    entity = session.get(Entity, observation.entity_id)
    document = session.get(Document, observation.document_id)
    source = session.get(Source, document.source_id) if document else None
    path = Path(storage) / document.content_hash if document else None
    verified = bool(path and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == document.content_hash)
    runs = []
    if document:
        for run in session.query(Run).order_by(Run.started_at):
            if run.manifest.get("document_id") == document.id:
                runs.append(record(run))
    return {
        "observation": record(observation),
        "entity": record(entity),
        "document": record(document),
        "source": record(source),
        "acquisition_runs": runs,
        "snapshot_verified": verified,
    }
