"""Small client for the Data Core API: plants, names, documents, facts and candidate facts.

The Workspace reads and writes Core data only through this client. It stores Core IDs, never copies,
and asks the Core for details. A candidate fact is a proposal: the Core runs its own source check,
matching (unclear names go to its human review), quality checks, and only then records a fact.

    CORE_URL    base URL of the Core (default http://127.0.0.1:8000)
    CORE_TOKEN  bearer token for the Core: its write token or one entry of its WRITE_IDENTITIES_JSON;
                also sent on reads, for a Core with REQUIRE_READ_AUTH=true
"""
import os
import httpx

PAGE = 1000

class CoreUnavailable(RuntimeError):
    """The Core could not be reached or failed; nothing was decided."""

class CoreRejected(ValueError):
    """The Core refused a request; the message is the Core's reason."""

class CoreClient:
    def __init__(self, base_url=None, token=None, transport=None, timeout=10.0):
        self.base_url = (base_url or os.getenv('CORE_URL', 'http://127.0.0.1:8000')).rstrip('/')
        token = os.getenv('CORE_TOKEN', '') if token is None else token
        self.http = httpx.Client(base_url=self.base_url + '/api', transport=transport, timeout=timeout,
                                 headers={'Authorization': 'Bearer ' + token} if token else {})
        self.memo = None

    def close(self):
        self.http.close()

    def cached(self):
        """A view of this client that reads each list once; use it for one request or batch."""
        view = CoreClient.__new__(CoreClient)
        view.base_url, view.http, view.memo = self.base_url, self.http, {}
        return view

    def _send(self, method, path, **kwargs):
        try: response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc: raise CoreUnavailable('Data Core unavailable: ' + type(exc).__name__) from None
        if response.status_code >= 500: raise CoreUnavailable(f'Data Core error {response.status_code}')
        return response

    def _json(self, response):
        if response.status_code >= 400:
            try: detail = response.json().get('detail')
            except ValueError: detail = None
            raise CoreRejected(detail if isinstance(detail, str) else f'Data Core refused the request ({response.status_code})')
        return response.json()

    def health(self):
        return self._json(self._send('GET', '/health'))

    def records(self, record_type, **filters):
        """Every record of a type, optionally filtered by column equality, in key order."""
        key = (record_type, tuple(sorted(filters.items())))
        if self.memo is not None and key in self.memo: return self.memo[key]
        rows, offset = [], 0
        while True:
            page = self._json(self._send('GET', '/records/' + record_type, params={**filters, 'offset': offset, 'limit': PAGE}))
            rows += page['records']
            offset += PAGE
            if offset >= page['total'] or not page['records']: break
        if self.memo is not None: self.memo[key] = rows
        return rows

    def record(self, record_type, identifier):
        """One record by ID, or None when the Core has no such record."""
        if not identifier: return None
        response = self._send('GET', f'/records/{record_type}/{identifier}')
        return None if response.status_code == 404 else self._json(response)

    # Plants, companies and their names
    def entities(self): return self.records('entities')
    def entity(self, identifier): return self.record('entities', identifier)
    def supersessions(self):
        """Replaced plant or company ID -> the ID that replaced it."""
        return {row['old_entity_id']: row['new_entity_id'] for row in self.records('supersessions')}

    # Documents (each Core document ID is one exact version) and facts
    def documents(self, **filters): return self.records('documents', **filters)
    def document(self, identifier): return self.record('documents', identifier)
    def document_content(self, identifier):
        """The exact saved bytes of a Core document; the Core checks them against its fingerprint."""
        response = self._send('GET', f'/documents/{identifier}/content')
        if response.status_code >= 400: self._json(response)
        return response.content
    def sources(self): return self.records('sources')
    def observations(self, **filters): return self.records('observations', **filters)
    def observation(self, identifier): return self.record('observations', identifier)
    def relationships(self): return self.records('relationships')
    def first_audited(self, record_id):
        """When the Core's change history first mentions a record, or None."""
        return min((row['created_at'] for row in self.records('audit', record_id=record_id)), default=None)

    # Candidate facts
    def propose_fact(self, document_id, extraction):
        """Send a candidate fact with its source document. The Core extracts it from its saved copy,
        matches the plant name and checks quality; the result lists the candidates and their status."""
        return self._json(self._send('POST', f'/documents/{document_id}/extract', json=extraction, timeout=60.0))
