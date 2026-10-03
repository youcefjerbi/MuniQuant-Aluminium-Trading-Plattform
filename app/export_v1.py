"""CommodityEvidencePackage v1 compatibility export: one JSONL record per active observation."""
from collections import defaultdict
from pathlib import Path
import hashlib
from sqlalchemy import select

from .models import Document, Entity, Observation, QualityCheckResult, QualityRun, Source
from .quality import quality_status

PACKAGE_VERSION = "1.0.0"
PROHIBITED_FIELDS = frozenset({
    "impact_score", "surprise_score", "market_state", "analogue_score", "supply_pressure",
    "price_prediction", "procurement_signal", "trading_signal", "factor_weight", "alpha",
})


def iter_cep_v1(session, storage):
    entities = {item.id: item for item in session.scalars(select(Entity)).all()}
    documents = {item.id: item for item in session.scalars(select(Document)).all()}
    sources = {item.id: item for item in session.scalars(select(Source)).all()}
    latest = session.scalar(select(QualityRun).order_by(QualityRun.started_at.desc()).limit(1))
    findings = defaultdict(list)
    if latest:
        for item in session.scalars(select(QualityCheckResult).where(QualityCheckResult.quality_run_id == latest.id)):
            findings[item.subject_id].append(item)
    for observation in session.scalars(select(Observation).order_by(Observation.entity_id, Observation.attribute, Observation.valid_from)):
        if observation.superseded_by_id:
            continue
        entity = entities[observation.entity_id]
        document = documents[observation.document_id]
        source = sources[document.source_id]
        path = Path(storage) / document.content_hash
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != document.content_hash:
            raise ValueError(f"Evidence snapshot missing or corrupted: {document.id}")
        related = findings.get(observation.id, []) + findings.get(entity.id, []) + findings.get(document.id, [])
        record = {
            "package_version": PACKAGE_VERSION,
            "pipeline_version": "0.1.0",
            "external_entity_id": entity.id,
            "entity_type": entity.kind,
            "canonical_name": entity.name,
            "aliases": entity.aliases,
            "facility_type": entity.facility_type,
            "country": entity.country,
            "region": entity.region or None,
            "attribute_type": observation.attribute,
            "reported_value": observation.reported_value,
            "reported_unit": observation.reported_unit,
            "normalized_value": None if observation.normalized_value is None else format(observation.normalized_value, ".15g"),
            "normalized_unit": observation.normalized_unit,
            "valid_from": observation.valid_from,
            "valid_to": observation.valid_to,
            "published_at": document.published_at,
            "retrieved_at": document.retrieved_at,
            "source_id": source.id,
            "source_name": source.name,
            "document_id": document.id,
            "document_version": document.version,
            "content_hash": document.content_hash,
            "evidence_reference": observation.evidence_reference,
            "resolution_status": "resolved",
            "quality_status": quality_status(related),
            "quality_findings": sorted({item.check_code for item in related}),
        }
        if PROHIBITED_FIELDS & record.keys():
            raise ValueError("Prohibited analytical field in CEP v1 export")
        yield record
