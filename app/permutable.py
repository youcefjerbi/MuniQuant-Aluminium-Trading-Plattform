"""Permutable AI as a licensed lead source: factual events and headlines only.

Scope follows the 12-week plan (p.25) and the Market Data Scope (section 7): only the
event and event-headline feeds are captured. Vendor analytics (sentiment indices,
direction/impact scores, signals, forecasts) are never parsed into tables or exported;
they survive only inside the exact response bytes preserved as snapshots. A lead points a
curator to an industrial change; any observation must cite a primary source.

Responses, saved copies and leads live in the Workspace's lead store. Plant names to match come
from the Data Core through its API; a confirmed lead keeps Core references to the primary-source
document and the fact it supports.

    python -m app.permutable setup
    python -m app.permutable capture --feed events --mode historical --since 2026-07-01
    python -m app.permutable poll            # live events + headlines; schedule every 15 min
    python -m app.permutable refresh-search  # pick up plant renames in the Core; schedule hourly
"""
import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urlencode
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from . import acquisition
from .core_client import CoreUnavailable
from .domain import canonical
from .models import LeadSource as Source, LeadSourceAccess as SourceAccess, LeadDocument as Document, Lead, LeadRevision, LeadHeadline, LeadRun as Run, Audit, now
from .pipeline import snapshot_bytes, logical_hash
from .schemas import RetrievalIn, PermutableSourceIn, PermutableCaptureIn, LeadDecisionIn
from .services import record

HOST = 'copilot-api.permutable.ai'
BASE = 'https://' + HOST + '/v1'
ADAPTER = 'permutable-api-v1'
PARSER_VERSION = 'permutable-leads-1.0.0'
SOURCE_ID = str(uuid5(NAMESPACE_URL, 'muniquant:source:permutable-ai'))
PATHS = {'events': '/events/feed/{mode}/ticker/{ticker}', 'event_headlines': '/event_headlines/feed/{mode}/ticker/{ticker}',
         'ticker_info': '/ticker/{ticker}/info', 'event_topics': '/events/topics/ticker/{ticker}'}
# Reference responses (instrument definition, topic taxonomy) are preserved as provenance, not parsed into leads.
REFERENCE = {'ticker_info', 'event_topics'}
PAGE_LIMIT = 500
# Factual fields only. direction, impact and other vendor scores are deliberately not read.
EVENT_FACTS = ('event_name', 'event_date', 'summary', 'topic_name', 'event_type', 'last_updated')
HEADLINE_FACTS = ('headline', 'source_name', 'link', 'published_at', 'language')
TRANSITIONS = {'new': {'follow_up', 'dismissed', 'confirmed'}, 'follow_up': {'dismissed', 'confirmed'}}
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?)?(Z|[+-]\d{2}:?\d{2})?')

class LeadConflict(Exception):
    """A lead decision that is final or out of order."""

def feed_url(feed, mode, ticker, start_date=None, end_date=None, next_token=None):
    if feed in REFERENCE: return BASE + PATHS[feed].format(ticker=ticker)
    params = {'event_type': 'Asset', 'limit': PAGE_LIMIT}
    if start_date: params['start_date'] = start_date.isoformat()
    if end_date: params['end_date'] = end_date.isoformat()
    if next_token: params['next_token'] = next_token
    # Sorted parameters keep one stable URL per request, so unchanged responses deduplicate.
    return BASE + PATHS[feed].format(mode=mode, ticker=ticker) + '?' + urlencode(sorted(params.items()))

def feed_of(document):
    path = document.original_url.removeprefix(BASE).split('?')[0]
    if path.startswith('/event_headlines/feed/'): return 'event_headlines'
    if path.startswith('/events/feed/'): return 'events'
    if path.startswith('/events/topics/'): return 'event_topics'
    return 'ticker_info'

def latest_policy(s):
    return s.scalar(select(SourceAccess).where(SourceAccess.source_id == SOURCE_ID).order_by(SourceAccess.decided_at.desc(), SourceAccess.id.desc()))

def register_source(s, actor, data=None):
    """Idempotently register Permutable as a permitted, credentialed, lead-only source."""
    data = data or PermutableSourceIn()
    source = s.get(Source, SOURCE_ID)
    if not source:
        source = Source(id=SOURCE_ID, name='Permutable AI licensed event feed', publisher='Permutable AI', source_type='commercial', url=BASE,
                        access_status='permitted', notes='Licensed commercial event and headline data. Lead-only: points curators to industrial changes and is never cited as observation evidence. Vendor sentiment, impact and signal fields are not ingested.')
        s.add(source); s.flush()
        s.add(Audit(actor=actor, action='create', record_id=source.id, detail={'type': 'sources'}))
    acquisition.check_credential_binding(data.credential_ref, [HOST])
    policy = latest_policy(s)
    if policy and policy.status != 'permitted':
        # Re-running setup must never silently overturn a reviewer's restriction or pending review.
        s.rollback(); raise ValueError('Permutable access is ' + policy.status + '; record a new access decision for the lead source first')
    if not policy or policy.credential_ref != data.credential_ref:
        previous = policy
        policy = SourceAccess(source_id=SOURCE_ID, status='permitted', allowed_hosts=previous.allowed_hosts if previous else [HOST],
                              basis=previous.basis if previous else data.basis, retention=previous.retention if previous else data.retention,
                              reviewer=actor, credential_ref=data.credential_ref, auth_header='x-api-key')
        s.add(policy); source.access_status = 'permitted'; s.flush()
        s.add(Audit(actor=actor, action='access_decision', record_id=policy.id, detail={'type': 'source_access', 'usage_scope': 'leads_only', 'credential_ref': data.credential_ref}))
    s.commit()
    return source, policy

def record_access(s, actor, data):
    """An audited access decision for the lead source: restrict, re-review or permit it again."""
    source = s.get(Source, SOURCE_ID)
    if not source: raise LookupError('Register the Permutable source first')
    values = data.model_dump()
    previous = latest_policy(s)
    # A re-review that omits the credential fields keeps them; dropping them needs an explicit value.
    if previous and 'credential_ref' not in data.model_fields_set and 'auth_header' not in data.model_fields_set:
        values['credential_ref'], values['auth_header'] = previous.credential_ref, previous.auth_header
    acquisition.check_credential_binding(values['credential_ref'], values['allowed_hosts'])
    policy = SourceAccess(source_id=SOURCE_ID, **values, reviewer=actor)
    s.add(policy); source.access_status = data.status; s.flush()
    s.add(Audit(actor=actor, action='access_decision', record_id=policy.id, detail={'type': 'source_access', 'usage_scope': 'leads_only'}))
    s.commit()
    return policy

def _text(value, limit):
    if not isinstance(value, str): return None
    value = ' '.join(value.split())
    return value[:limit] or None

def _stamp(value):
    return value if isinstance(value, str) and STAMP.fullmatch(value) else None

def _instant(value):
    """Vendor timestamp as an aware UTC datetime; naive values are UTC per the vendor documentation."""
    from datetime import datetime, timezone
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def _supersedes(new, current):
    """Whether a revision updated at `new` becomes the lead's current view; ties go to the latest capture."""
    if current is None: return True
    if new is None: return False
    return _instant(new) >= _instant(current)

def parse_feed(raw, feed):
    """Deterministic factual view of one preserved response; the replay check reruns this."""
    try: body = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc: raise ValueError('Permutable response is not valid UTF-8 JSON') from exc
    items = body.get('data') if isinstance(body, dict) else body
    if not isinstance(items, list): raise ValueError('Unexpected Permutable response shape')
    if len(items) > 1000: raise ValueError('At most 1000 records per page')
    rows = []
    for item in items:
        if not isinstance(item, dict): raise ValueError('Unexpected Permutable record')
        raw_id = item.get('event_id')
        event_id = _text(str(raw_id) if isinstance(raw_id, int) and not isinstance(raw_id, bool) else raw_id, 128)
        if not event_id: raise ValueError('Permutable record has no event_id')
        if feed == 'events':
            rows.append({'event_id': event_id, 'event_name': _text(item.get('event_name'), 500) or '(untitled event)', 'event_date': _stamp(item.get('event_date')),
                         'summary': _text(item.get('summary'), 4000) or '', 'topic_name': _text(item.get('topic_name'), 200),
                         'event_type': _text(item.get('event_type'), 32), 'last_updated': _stamp(item.get('last_updated'))})
        else:
            headline = _text(item.get('headline'), 1000)
            if not headline: continue
            link = _text(item.get('link'), 2048)
            if link and not re.match(r'https?://[^\s]+$', link): link = None
            rows.append({'event_id': event_id, 'headline': headline, 'source_name': _text(item.get('source_name'), 200), 'link': link,
                         'published_at': _stamp(item.get('publication_time')), 'language': _text(item.get('language'), 16)})
    return rows

def entity_index(core):
    """Canonical names and aliases of current Core entities; superseded identities map to survivors."""
    links = core.supersessions()
    def current(identifier):
        seen = set()
        while identifier in links and identifier not in seen:
            seen.add(identifier); identifier = links[identifier]
        return identifier
    index = {}
    for entity in core.entities():
        for name in [entity['name'], *entity['aliases']]:
            key = canonical(name)
            # Very short names (e.g. "QA") match too much free text to be a useful pointer.
            if len(key) >= 4: index.setdefault(key, set()).add(current(entity['id']))
    return index

def match_entities(index, texts):
    haystack = ' ' + canonical(' '.join(t for t in texts if t)) + ' '
    return sorted({identifier for key, ids in index.items() if ' ' + key + ' ' in haystack for identifier in ids})

def _lead(s, event_id, ticker, seen_at):
    identifier = str(uuid5(NAMESPACE_URL, 'muniquant:lead:' + SOURCE_ID + ':' + event_id))
    lead = s.get(Lead, identifier)
    if lead:
        lead.last_seen_at = max(lead.last_seen_at, seen_at)
        return lead, False
    lead = Lead(id=identifier, source_id=SOURCE_ID, external_id=event_id, ticker=ticker, status='new', first_seen_at=seen_at, last_seen_at=seen_at)
    s.add(lead); s.flush()
    return lead, True

def derive(s, storage, document, ticker, core):
    """Turn one preserved response into leads, distinct event revisions and headlines."""
    if document.source_id != SOURCE_ID: raise ValueError('Not a Permutable lead document')
    feed = feed_of(document)
    if feed in REFERENCE: return {'leads_created': 0, 'revisions_added': 0, 'headlines_added': 0}
    rows = parse_feed(snapshot_bytes(storage, document), feed)
    counts = {'leads_created': 0, 'revisions_added': 0, 'headlines_added': 0}
    index = entity_index(core) if feed == 'events' else None
    touched = set()
    for row in rows:
        lead, created = _lead(s, row['event_id'], ticker, document.retrieved_at)
        touched.add(lead.id)
        counts['leads_created'] += created
        facts = {key: row[key] for key in (EVENT_FACTS if feed == 'events' else HEADLINE_FACTS)}
        digest = logical_hash(facts)
        model = LeadRevision if feed == 'events' else LeadHeadline
        # Each distinct factual state is kept once, with the first snapshot that carried it.
        existing = s.scalar(select(model).where(model.lead_id == lead.id, model.content_hash == digest))
        if feed == 'events':
            if existing: matched = existing.matched_entity_ids
            else:
                matched = match_entities(index, [facts['event_name'], facts['summary']])
                s.add(LeadRevision(id=str(uuid5(NAMESPACE_URL, f'muniquant:lead_revision:{lead.id}:{digest}')), lead_id=lead.id, document_id=document.id, content_hash=digest,
                                   parser_version=PARSER_VERSION, event_name=facts['event_name'], event_date=facts['event_date'], summary=facts['summary'], topic_name=facts['topic_name'],
                                   event_type=facts['event_type'], vendor_updated_at=facts['last_updated'], matched_entity_ids=matched))
                counts['revisions_added'] += 1
            # A backfill may deliver an older state after a newer one, and a vendor may revert to an earlier
            # state: the current view follows the vendor timestamp, with ties going to the latest capture.
            if _supersedes(facts['last_updated'], lead.vendor_updated_at):
                lead.event_date, lead.topic_name, lead.vendor_updated_at, lead.matched_entity_count, lead.current_revision_hash = facts['event_date'], facts['topic_name'], facts['last_updated'], len(matched), digest
        elif not existing:
            common = {'id': str(uuid5(NAMESPACE_URL, f'muniquant:lead_headline:{lead.id}:{digest}')), 'lead_id': lead.id, 'document_id': document.id, 'content_hash': digest, 'parser_version': PARSER_VERSION}
            s.add(LeadHeadline(**common, **facts))
            counts['headlines_added'] += 1
        s.flush()
    refresh_search(s, core, touched)
    if any(counts.values()):
        s.add(Run(status='success', pipeline_version='1.0.0', manifest={'adapter': 'permutable-leads', 'parser_version': PARSER_VERSION, 'document_id': document.id,
                                                                          'content_hash': document.content_hash, 'feed': feed, 'ticker': ticker, **counts}))
    s.flush()
    return counts

def capture(s, storage, actor, data, core, fetch=None, pause=0.1):
    """Fetch one feed (paging historical windows), preserve every page and derive leads."""
    if not s.get(Source, SOURCE_ID): raise ValueError('Register the Permutable source first')
    fetch = fetch or acquisition.fetch_once
    summary = {'feed': data.feed, 'mode': data.mode, 'ticker': data.ticker, 'pages': 0, 'new_documents': 0, 'duplicate_documents': 0,
               'leads_created': 0, 'revisions_added': 0, 'headlines_added': 0, 'document_ids': []}
    token = None
    for page in range(data.max_pages):
        url = feed_url(data.feed, data.mode, data.ticker, data.start_date, data.end_date, token)
        title = f'Permutable {data.feed} {data.mode} {data.ticker}' + (f' page {page + 1}' if data.mode == 'historical' else '')
        doc, duplicate, _ = acquisition.acquire_remote(s, storage, RetrievalIn(source_id=SOURCE_ID, url=url, title=title), actor, fetch, adapter=ADAPTER)
        summary['pages'] += 1
        summary['duplicate_documents' if duplicate else 'new_documents'] += 1
        summary['document_ids'].append(doc.id)
        if data.feed in REFERENCE: break
        document_id, content_hash = doc.id, doc.content_hash
        for attempt in (1, 2):
            try:
                counts = derive(s, storage, doc, data.ticker, core); break
            except (ValueError, IntegrityError, CoreUnavailable) as exc:
                # The preserved response stays registered; a failure is logged without partial leads.
                s.rollback()
                if isinstance(exc, IntegrityError) and attempt == 1:
                    doc = s.get(Document, document_id); continue  # a concurrent capture created the same lead first
                error = 'Concurrent capture conflict; retry' if isinstance(exc, IntegrityError) else str(exc)[:500]
                s.add(Run(status='failed', pipeline_version='1.0.0', manifest={'adapter': 'permutable-leads', 'parser_version': PARSER_VERSION, 'document_id': document_id, 'content_hash': content_hash, 'error': error}))
                s.commit(); raise (CoreUnavailable if isinstance(exc, CoreUnavailable) else ValueError)(error) from None
        for key, value in counts.items(): summary[key] += value
        s.commit()
        if data.mode == 'live': break
        body = json.loads(snapshot_bytes(storage, doc))
        token = body.get('next_token') if isinstance(body, dict) and body.get('has_more') else None
        if not token: break
        time.sleep(pause)
    return summary

def replay_document(s, storage, document_id):
    """Re-parse a preserved response and prove stored lead facts equal the parser output."""
    doc = s.get(Document, document_id)
    if not doc or doc.source_id != SOURCE_ID: raise ValueError('Unknown Permutable document')
    feed = feed_of(doc)
    if feed in REFERENCE: raise ValueError('Reference responses carry no derived leads to replay')
    rows = parse_feed(snapshot_bytes(storage, doc), feed)
    parsed = {logical_hash({key: row[key] for key in (EVENT_FACTS if feed == 'events' else HEADLINE_FACTS)}) for row in rows}
    if feed == 'events':
        stored = [(r.content_hash, r.parser_version, {'event_name': r.event_name, 'event_date': r.event_date, 'summary': r.summary, 'topic_name': r.topic_name, 'event_type': r.event_type, 'last_updated': r.vendor_updated_at})
                  for r in s.scalars(select(LeadRevision).where(LeadRevision.document_id == doc.id))]
    else:
        stored = [(h.content_hash, h.parser_version, {key: getattr(h, key) for key in HEADLINE_FACTS}) for h in s.scalars(select(LeadHeadline).where(LeadHeadline.document_id == doc.id))]
    for digest, parser, facts in stored:
        if parser != PARSER_VERSION: raise ValueError('Unsupported lead parser version')
        if logical_hash(facts) != digest or digest not in parsed: raise ValueError('Stored lead facts differ from the preserved response')
    return {'document_id': doc.id, 'content_hash': doc.content_hash, 'parser_version': PARSER_VERSION, 'feed': feed, 'records': len(rows), 'verified': len(stored), 'equivalent': True}

def decide(s, lead_id, data, actor, core):
    """Audited triage: new -> follow_up -> confirmed (with primary evidence) or dismissed.

    The primary-source document and its fact are Core records; lead feeds are never Core sources."""
    lead = s.get(Lead, lead_id)
    if not lead: raise LookupError('Lead not found')
    if data.status not in TRANSITIONS.get(lead.status, set()): raise LeadConflict(f'Lead is {lead.status}; {data.status} is not allowed')
    if data.status == 'confirmed':
        doc = core.document(data.primary_document_id)
        if not doc: raise ValueError('Unknown primary-source document')
        if data.observation_id:
            obs = core.observation(data.observation_id)
            if not obs or obs['document_id'] != doc['id']: raise ValueError('Observation must cite the confirming primary-source document')
    changed = s.execute(update(Lead).where(Lead.id == lead_id, Lead.status == lead.status).values(
        status=data.status, reviewer=actor, reason=data.reason, decided_at=now(), primary_document_id=data.primary_document_id, observation_id=data.observation_id))
    if changed.rowcount != 1: raise LeadConflict('Lead was decided concurrently; refresh and retry')
    s.add(Audit(actor=actor, action='lead_decision', record_id=lead_id, detail=data.model_dump()))
    s.commit(); s.refresh(lead)
    return lead

def concat_ws(*parts):
    """PostgreSQL concat_ws(' ', ...): NULL parts are skipped, empty strings are kept."""
    return ' '.join(part for part in parts if part is not None)

def refresh_search(s, core, lead_ids=None):
    """Recompute the search projection of the given leads (all when None) from their current revision,
    their headlines and the current Core names of matched plants. Returns the number of leads changed.

    Before the split, PostgreSQL triggers kept this text, including a trigger on the plant table that
    now lives in the Core; the Core cannot call the Workspace, so a rename reaches the projection on the
    next refresh-search run."""
    if lead_ids is not None and not lead_ids: return 0
    query = select(Lead)
    if lead_ids is not None: query = query.where(Lead.id.in_(sorted(lead_ids)))
    leads = s.scalars(query.order_by(Lead.id)).all()
    if not leads: return 0
    names = {entity['id']: entity['name'] for entity in core.entities()}
    ids = [lead.id for lead in leads]
    revisions_of, headlines_of = {}, {}
    for revision in s.scalars(select(LeadRevision).where(LeadRevision.lead_id.in_(ids)).order_by(LeadRevision.recorded_at.desc(), LeadRevision.id)):
        revisions_of.setdefault(revision.lead_id, []).append(revision)
    for headline in s.scalars(select(LeadHeadline).where(LeadHeadline.lead_id.in_(ids)).order_by(LeadHeadline.id)):
        headlines_of.setdefault(headline.lead_id, []).append(headline.headline)
    changed = 0
    for lead in leads:
        revisions = revisions_of.get(lead.id, [])
        revision = next((r for r in revisions if r.content_hash == lead.current_revision_hash), revisions[0] if revisions else None)
        matched = [names[i] for i in sorted(revision.matched_entity_ids) if i in names] if revision else []
        text = concat_ws(lead.topic_name, concat_ws(revision.event_name, revision.summary, ' '.join(matched) or None) if revision else None,
                         ' '.join(headlines_of[lead.id]) if lead.id in headlines_of else None)
        if lead.search_text != text:
            lead.search_text = text; changed += 1
    s.flush()
    return changed

def list_leads(s, core, status=None, offset=0, limit=100, topic=None, matched=None, search=None):
    from .event_search import rank, tokens
    from sqlalchemy import text
    search = search.strip() if search else ""
    filters = []
    if status: filters.append(Lead.status == status)
    if topic: filters.append(Lead.topic_name == topic)
    if matched is not None: filters.append(Lead.matched_entity_count > 0 if matched else Lead.matched_entity_count == 0)
    query = select(Lead).where(*filters).order_by(Lead.event_date.desc().nulls_last(), Lead.last_seen_at.desc(), Lead.id)
    indexed = bool(search and s.bind.dialect.name == 'postgresql')
    scores = {}
    if indexed:
        # The expression exactly matches the GIN index; filtering, ranking and
        # pagination happen in PostgreSQL, before any ORM objects are hydrated.
        vector = func.to_tsvector(text("'simple'::regconfig"), Lead.search_text)
        terms = tokens(search)
        tsquery = func.to_tsquery(text("'simple'::regconfig"), ' | '.join(terms))
        filters.append(vector.op('@@')(tsquery))
        score = func.ts_rank_cd(vector, tsquery, 32)
        rows = s.execute(select(Lead, score.label('score')).where(*filters)
                         .order_by(score.desc(), Lead.event_date.desc().nulls_last(),
                                   Lead.last_seen_at.desc(), Lead.id)
                         .offset(offset).limit(limit)).all()
        page = [row[0] for row in rows]
        scores = {row[0].id: float(row[1]) for row in rows}
    else:
        page = s.scalars(query if search else query.offset(offset).limit(limit)).all()
    names = {}
    ids = [lead.id for lead in page]
    revisions_of, headlines_of = {}, {}
    # Two batched queries for the whole page instead of two per lead.
    for revision in s.scalars(select(LeadRevision).where(LeadRevision.lead_id.in_(ids)).order_by(LeadRevision.recorded_at.desc(), LeadRevision.id)):
        revisions_of.setdefault(revision.lead_id, []).append(revision)
    for item in s.scalars(select(LeadHeadline).where(LeadHeadline.lead_id.in_(ids)).order_by(LeadHeadline.published_at.desc(), LeadHeadline.id)):
        headlines_of.setdefault(item.lead_id, []).append(item)
    entity_ids = {i for revisions in revisions_of.values() for r in revisions for i in r.matched_entity_ids}
    if entity_ids:
        names = {e['id']: e['name'] for e in core.entities() if e['id'] in entity_ids}
    result = []
    search_texts = []
    for lead in page:
        revisions = revisions_of.get(lead.id, [])
        headlines = headlines_of.get(lead.id, [])[:10]
        latest = next((r for r in revisions if r.content_hash == lead.current_revision_hash), revisions[0] if revisions else None)
        search_texts.append(' '.join([latest.event_name if latest else '', latest.summary if latest else '', lead.topic_name or '', *[names.get(i, '') for i in (latest.matched_entity_ids if latest else [])], *[h.headline for h in headlines_of.get(lead.id, [])]]))
        result.append({**{k:v for k,v in record(lead).items() if k != 'search_text'}, 'revision_count': len(revisions), 'latest_revision': record(latest) if latest else None,
                       'matched_entities': [{'id': i, 'name': names.get(i)} for i in (latest.matched_entity_ids if latest else [])],
                       'headlines': [record(h) for h in headlines]})
    total = s.scalar(select(func.count()).select_from(Lead).where(*filters))
    if indexed:
        for item, content in zip(result, search_texts):
            item['similarity_score'] = scores[item['id']]
            item['matched_terms'] = sorted(set(tokens(search)) & set(tokens(content)))
    elif search:
        ranked = [{**result[index], 'similarity_score': score, 'matched_terms': terms} for index, score, terms in rank(search, search_texts)]
        total = len(ranked)
        result = ranked[offset:offset + limit]
    topics = sorted(t for t in s.scalars(select(Lead.topic_name).distinct()) if t)
    return {'leads': result, 'total': total, 'search': search, 'ranking': 'postgres-fts-v1' if indexed else ('tfidf-cosine-v1' if search else 'newest'), 'offset': offset, 'limit': limit, 'topics': topics}

def main():
    from sqlalchemy.orm import Session
    from .db import make_engine, DATABASE_URL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('setup', help='register the licensed lead-only source and its credential reference')
    setup.add_argument('--credential-ref', default='PERMUTABLE_API_KEY')
    setup.add_argument('--tickers', default=os.getenv('PERMUTABLE_TICKERS', 'ALI_COM'), help='reference responses (instrument, topics) to preserve')
    one = commands.add_parser('capture', help='capture one feed')
    one.add_argument('--feed', choices=sorted(PATHS), required=True)
    one.add_argument('--mode', choices=['live', 'historical'], default='live')
    one.add_argument('--ticker', default='ALI_COM')
    one.add_argument('--since'); one.add_argument('--until')
    one.add_argument('--max-pages', type=int, default=10)
    poll = commands.add_parser('poll', help='capture live events and headlines for each ticker')
    poll.add_argument('--tickers', default=os.getenv('PERMUTABLE_TICKERS', 'ALI_COM'))
    commands.add_parser('refresh-search', help='recompute lead search text with the current Core plant names')
    args = parser.parse_args()
    actor = os.getenv('WRITE_ACTOR', 'permutable-operator')
    storage = os.getenv('SNAPSHOT_DIR', 'data/snapshots')
    from .core_client import CoreClient
    core = CoreClient().cached()
    with Session(make_engine(DATABASE_URL)) as s:
        if args.command == 'refresh-search':
            changed = refresh_search(s, core); s.commit()
            print(json.dumps({'leads_changed': changed}, indent=2)); return
        if args.command == 'setup':
            source, policy = register_source(s, actor, PermutableSourceIn(credential_ref=args.credential_ref))
            print(json.dumps({'source_id': source.id, 'access_decision_id': policy.id, 'usage_scope': 'leads_only', 'credential_ref': policy.credential_ref}, indent=2))
            jobs = [PermutableCaptureIn(feed=feed, ticker=ticker.strip()) for ticker in args.tickers.split(',') if ticker.strip() for feed in sorted(REFERENCE)]
        elif args.command == 'capture':
            jobs = [PermutableCaptureIn(feed=args.feed, mode=args.mode, ticker=args.ticker, start_date=args.since, end_date=args.until, max_pages=args.max_pages)]
        else:
            jobs = [PermutableCaptureIn(feed=feed, ticker=ticker.strip()) for ticker in args.tickers.split(',') if ticker.strip() for feed in ('events', 'event_headlines')]
        results, failed = [], False
        for job in jobs:
            try: results.append(capture(s, storage, actor, job, core))
            # A concurrent poll can win the race for a new lead; the next scheduled run picks up the rest.
            except (ValueError, IntegrityError, CoreUnavailable) as exc:
                s.rollback(); failed = True
                results.append({'feed': job.feed, 'ticker': job.ticker, 'error': str(exc)})
        print(json.dumps(results, indent=2))
        if failed: sys.exit(1)

if __name__ == '__main__': main()
