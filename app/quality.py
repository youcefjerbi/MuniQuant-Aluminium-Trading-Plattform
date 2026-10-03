"""Versioned data-quality runs over persisted claims and relationships."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from .models import Document, Observation, QualityCheckResult, QualityRun, Relationship

RULESET_VERSION = "1.0.0"
SEVERITY_ORDER = {"INFO": 0, "WARN": 1, "ERROR": 2, "BLOCK": 3}


def _finding(code, severity, subject_type, subject_id, message, details=None):
    return QualityCheckResult(
        check_code=code,
        severity=severity,
        subject_type=subject_type,
        subject_id=subject_id,
        message=message,
        details=details or {},
    )


def evaluate(session):
    findings = []
    documents = {item.id: item for item in session.scalars(select(Document)).all()}
    observations = session.scalars(select(Observation)).all()

    by_series = defaultdict(list)
    for observation in observations:
        if observation.superseded_by_id:
            continue
        document = documents.get(observation.document_id)
        if document and not document.published_at:
            findings.append(_finding("MISSING_PUBLICATION_DATE", "WARN", "observation", observation.id,
                                     "Evidence document has no publication date"))
        if not observation.evidence_reference.strip():
            findings.append(_finding("MISSING_EVIDENCE_LOCATOR", "INFO", "observation", observation.id,
                                     "Observation has no locator inside its evidence"))
        if observation.attribute == "capacity" and observation.normalized_value is None:
            findings.append(_finding("NOT_NORMALIZED", "ERROR", "observation", observation.id,
                                     "Capacity has no normalized representation"))
        if observation.normalized_value is not None:
            by_series[(observation.entity_id, observation.attribute, observation.valid_from)].append(observation)

    for (entity_id, attribute, valid_from), group in by_series.items():
        values = {Decimal(str(item.normalized_value)) for item in group}
        if len(values) > 1:
            detail = {"values": sorted(str(value) for value in values), "observation_ids": [item.id for item in group]}
            for item in group:
                findings.append(_finding("CONFLICTING_SOURCES", "WARN", "observation", item.id,
                                         f"Conflicting {attribute} values valid from {valid_from}", detail))

    relationships = [item for item in session.scalars(select(Relationship)).all() if not item.superseded_by_id]
    by_facility = defaultdict(list)
    for relationship in relationships:
        if relationship.role == "OWNS" and relationship.percentage is not None:
            by_facility[relationship.facility_id].append(relationship)
    for facility_id, group in by_facility.items():
        for point in sorted({item.valid_from for item in group}):
            active = [item for item in group if item.valid_from <= point and (item.valid_to is None or item.valid_to >= point)]
            total = sum(Decimal(str(item.percentage)) for item in active)
            if total > 100:
                findings.append(_finding("OWNERSHIP_OVER_100", "ERROR", "facility", facility_id,
                                         f"Known ownership totals {total}% at {point}",
                                         {"relationship_ids": [item.id for item in active]}))
    return findings


def run_quality(session):
    run = QualityRun(ruleset_version=RULESET_VERSION, started_at=datetime.now(timezone.utc).isoformat(), status="running")
    session.add(run)
    session.flush()
    findings = evaluate(session)
    counts = defaultdict(int)
    for finding in findings:
        finding.quality_run_id = run.id
        counts[finding.severity] += 1
        session.add(finding)
    run.finished_at = datetime.now(timezone.utc).isoformat()
    run.status = "complete"
    run.summary = {"findings": len(findings), "by_severity": dict(counts)}
    session.flush()
    return run, findings


def quality_status(findings):
    worst = max((SEVERITY_ORDER[item.severity] for item in findings), default=-1)
    if worst < 0:
        return "PASS"
    return "WARN" if worst <= SEVERITY_ORDER["WARN"] else "FAIL"
