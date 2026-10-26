BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('851cabd681a0');
CREATE TABLE asset_dependency (
	id VARCHAR NOT NULL, 
	from_entity_id VARCHAR NOT NULL, 
	to_entity_id VARCHAR NOT NULL, 
	product VARCHAR(32) NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	document_id VARCHAR NOT NULL, 
	valid_from VARCHAR NOT NULL, 
	valid_to VARCHAR, 
	status VARCHAR(16) NOT NULL, 
	note VARCHAR NOT NULL, 
	synthetic INTEGER NOT NULL, 
	actor VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_dependency_distinct CHECK (from_entity_id <> to_entity_id), 
	CONSTRAINT ck_dependency_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE TABLE asset_location (
	id VARCHAR NOT NULL, 
	entity_id VARCHAR NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	document_id VARCHAR NOT NULL, 
	precision VARCHAR(32) NOT NULL, 
	synthetic INTEGER NOT NULL, 
	actor VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_asset_latitude CHECK (latitude BETWEEN -90 AND 90), 
	CONSTRAINT ck_asset_longitude CHECK (longitude BETWEEN -180 AND 180)
);
CREATE TABLE audit (
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	actor VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	record_id VARCHAR NOT NULL, 
	detail JSON NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE investigation (
	id VARCHAR NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_investigation_status CHECK (status IN ('investigating','confirmed','disproven','resolved','inconclusive'))
);
CREATE TABLE investigation_entry (
	id VARCHAR NOT NULL, 
	case_id VARCHAR NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	text VARCHAR NOT NULL, 
	document_id VARCHAR, 
	hypothesis_id VARCHAR, 
	stance VARCHAR(16) NOT NULL, 
	source_url VARCHAR, 
	passage VARCHAR NOT NULL, 
	published_at VARCHAR, 
	actor VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES investigation (id), 
	FOREIGN KEY(hypothesis_id) REFERENCES investigation_entry (id)
);
CREATE TABLE investigation_revision (
	id VARCHAR NOT NULL, 
	case_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	actor VARCHAR NOT NULL, 
	snapshot JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES investigation (id), 
	CONSTRAINT uq_investigation_version UNIQUE (case_id, version)
);
CREATE TABLE investigation_task (
	id VARCHAR NOT NULL, 
	case_id VARCHAR NOT NULL, 
	question VARCHAR NOT NULL, 
	assignee VARCHAR NOT NULL, 
	due_at VARCHAR, 
	status VARCHAR(16) NOT NULL, 
	answer VARCHAR NOT NULL, 
	created_by VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_by VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES investigation (id)
);
CREATE TABLE investigation_task_evidence (
	task_id VARCHAR NOT NULL, 
	entry_id VARCHAR NOT NULL, 
	PRIMARY KEY (task_id, entry_id), 
	FOREIGN KEY(entry_id) REFERENCES investigation_entry (id), 
	FOREIGN KEY(task_id) REFERENCES investigation_task (id)
);
CREATE TABLE lead (
	id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	external_id VARCHAR(128) NOT NULL, 
	ticker VARCHAR(32) NOT NULL, 
	status VARCHAR NOT NULL, 
	first_seen_at VARCHAR NOT NULL, 
	last_seen_at VARCHAR NOT NULL, 
	event_date VARCHAR, 
	topic_name VARCHAR, 
	vendor_updated_at VARCHAR, 
	current_revision_hash VARCHAR(64), 
	matched_entity_count INTEGER DEFAULT '0' NOT NULL, 
	reviewer VARCHAR, 
	reason TEXT, 
	decided_at VARCHAR, 
	primary_document_id VARCHAR, 
	observation_id VARCHAR, 
	search_text TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_lead_confirmed_evidence CHECK (status <> 'confirmed' OR primary_document_id IS NOT NULL), 
	CONSTRAINT ck_lead_status CHECK (status IN ('new','follow_up','dismissed','confirmed')), 
	FOREIGN KEY(source_id) REFERENCES lead_source (id), 
	CONSTRAINT uq_lead_source_external UNIQUE (source_id, external_id)
);
CREATE TABLE lead_document (
	id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	original_url VARCHAR NOT NULL, 
	published_at VARCHAR, 
	retrieved_at VARCHAR NOT NULL, 
	media_type VARCHAR NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (version > 0), 
	FOREIGN KEY(source_id) REFERENCES lead_source (id), 
	UNIQUE (source_id, original_url, content_hash), 
	UNIQUE (source_id, original_url, version)
);
CREATE TABLE lead_document_version (
	document_id VARCHAR NOT NULL, 
	snapshot_hash VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (document_id), 
	CONSTRAINT ck_document_version_positive CHECK (version > 0), 
	FOREIGN KEY(document_id) REFERENCES lead_document (id), 
	FOREIGN KEY(snapshot_hash) REFERENCES lead_snapshot (content_hash)
);
CREATE TABLE lead_headline (
	id VARCHAR NOT NULL, 
	lead_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	parser_version VARCHAR NOT NULL, 
	headline TEXT NOT NULL, 
	source_name VARCHAR, 
	link VARCHAR(2048), 
	published_at VARCHAR, 
	language VARCHAR(16), 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES lead_document (id), 
	FOREIGN KEY(lead_id) REFERENCES lead (id), 
	CONSTRAINT uq_lead_headline_content UNIQUE (lead_id, content_hash)
);
CREATE TABLE lead_retrieval_attempt (
	id VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	url VARCHAR NOT NULL, 
	attempt INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	error VARCHAR, 
	http_status INTEGER, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_id) REFERENCES lead_run (id)
);
CREATE TABLE lead_revision (
	id VARCHAR NOT NULL, 
	lead_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	parser_version VARCHAR NOT NULL, 
	event_name TEXT NOT NULL, 
	event_date VARCHAR, 
	summary TEXT NOT NULL, 
	topic_name VARCHAR, 
	event_type VARCHAR, 
	vendor_updated_at VARCHAR, 
	matched_entity_ids JSON NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES lead_document (id), 
	FOREIGN KEY(lead_id) REFERENCES lead (id), 
	CONSTRAINT uq_lead_revision_content UNIQUE (lead_id, content_hash)
);
CREATE TABLE lead_run (
	id VARCHAR NOT NULL, 
	started_at VARCHAR NOT NULL, 
	pipeline_version VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	manifest JSON NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE lead_snapshot (
	content_hash VARCHAR(64) NOT NULL, 
	storage_reference VARCHAR NOT NULL, 
	byte_size INTEGER, 
	PRIMARY KEY (content_hash), 
	CONSTRAINT ck_snapshot_size CHECK (byte_size >= 0)
);
CREATE TABLE lead_source (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	publisher VARCHAR NOT NULL, 
	source_type VARCHAR NOT NULL, 
	url VARCHAR NOT NULL, 
	access_status VARCHAR NOT NULL, 
	notes TEXT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE lead_source_access (
	id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	allowed_hosts JSON NOT NULL, 
	basis TEXT NOT NULL, 
	retention TEXT NOT NULL, 
	reviewer VARCHAR NOT NULL, 
	decided_at VARCHAR NOT NULL, 
	credential_ref VARCHAR(64), 
	auth_header VARCHAR(64), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_source_access_status CHECK (status IN ('permitted','review_required','restricted')), 
	CONSTRAINT ck_source_access_credential CHECK ((credential_ref IS NULL) = (auth_header IS NULL)), 
	FOREIGN KEY(source_id) REFERENCES lead_source (id)
);
CREATE TABLE lead_source_document (
	source_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	PRIMARY KEY (source_id, document_id), 
	FOREIGN KEY(document_id) REFERENCES lead_document (id), 
	FOREIGN KEY(source_id) REFERENCES lead_source (id)
);
CREATE TABLE market_observations (
	id VARCHAR NOT NULL, 
	instrument VARCHAR NOT NULL, 
	exchange VARCHAR NOT NULL, 
	market VARCHAR NOT NULL, 
	contract_code VARCHAR, 
	prompt_date VARCHAR, 
	commodity VARCHAR NOT NULL, 
	grade VARCHAR, 
	region VARCHAR NOT NULL, 
	price_type VARCHAR NOT NULL, 
	value VARCHAR NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	unit VARCHAR NOT NULL, 
	effective_at VARCHAR NOT NULL, 
	published_at VARCHAR, 
	volume INTEGER, 
	open_interest INTEGER, 
	data_status VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	evidence_reference VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (open_interest IS NULL OR open_interest >= 0), 
	CHECK (volume IS NULL OR volume >= 0)
);
CREATE TABLE paper_accounts (
	id VARCHAR NOT NULL, 
	cash_cents BIGINT NOT NULL, 
	cursor INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (cash_cents >= 0), 
	CHECK (cursor >= 0 AND cursor < 120)
);
INSERT INTO "paper_accounts" VALUES('shared-pilot',10000000,60,0);
CREATE TABLE paper_orders (
	id INTEGER NOT NULL, 
	request_id VARCHAR NOT NULL, 
	instrument VARCHAR NOT NULL, 
	side VARCHAR NOT NULL, 
	order_type VARCHAR NOT NULL, 
	quantity INTEGER NOT NULL, 
	limit_cents INTEGER, 
	fill_cents INTEGER, 
	status VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	filled_at VARCHAR, 
	session_index INTEGER NOT NULL, 
	actor VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (side IN ('buy','sell')), 
	CHECK (status IN ('open','filled','cancelled','expired','settled')), 
	CHECK (quantity > 0), 
	UNIQUE (request_id)
);
CREATE TABLE paper_policy (
	id VARCHAR NOT NULL, 
	settings JSON NOT NULL, 
	actor VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE research_event (
	id VARCHAR NOT NULL, 
	external_key VARCHAR(256) NOT NULL, 
	instrument VARCHAR(64) NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	occurred_at VARCHAR NOT NULL, 
	known_at VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	historical INTEGER NOT NULL, 
	payload JSON NOT NULL, 
	chain JSON NOT NULL, 
	features JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (external_key)
);
CREATE TABLE research_outcome (
	id VARCHAR NOT NULL, 
	event_id VARCHAR NOT NULL, 
	entry_quote_id VARCHAR NOT NULL, 
	exit_quote_id VARCHAR NOT NULL, 
	return_fraction TEXT NOT NULL, 
	available_at VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_quote_id) REFERENCES research_quote (id), 
	FOREIGN KEY(event_id) REFERENCES research_event (id), 
	FOREIGN KEY(exit_quote_id) REFERENCES research_quote (id), 
	UNIQUE (event_id)
);
CREATE TABLE research_paper_account (
	id VARCHAR NOT NULL, 
	policy_id VARCHAR NOT NULL, 
	instrument VARCHAR(64) NOT NULL, 
	cash TEXT NOT NULL, 
	quantity TEXT NOT NULL, 
	peak_equity TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(policy_id) REFERENCES paper_policy (id)
);
CREATE TABLE research_paper_decision (
	id VARCHAR NOT NULL, 
	event_id VARCHAR NOT NULL, 
	policy_id VARCHAR NOT NULL, 
	quote_id VARCHAR, 
	action VARCHAR(8) NOT NULL, 
	reason TEXT NOT NULL, 
	details JSON NOT NULL, 
	actor VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_research_action CHECK (action IN ('BUY','SELL','HOLD')), 
	FOREIGN KEY(event_id) REFERENCES research_event (id), 
	FOREIGN KEY(policy_id) REFERENCES paper_policy (id), 
	FOREIGN KEY(quote_id) REFERENCES research_quote (id), 
	UNIQUE (event_id)
);
CREATE TABLE research_quote (
	id VARCHAR NOT NULL, 
	external_key VARCHAR(256) NOT NULL, 
	instrument VARCHAR(64) NOT NULL, 
	price TEXT NOT NULL, 
	observed_at VARCHAR NOT NULL, 
	known_at VARCHAR NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	source_reference TEXT NOT NULL, 
	historical INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_research_quote_positive CHECK (CAST(price AS NUMERIC) > 0), 
	UNIQUE (external_key)
);
CREATE INDEX ix_asset_dependency_from_entity_id ON asset_dependency (from_entity_id);
CREATE INDEX ix_asset_dependency_product ON asset_dependency (product);
CREATE INDEX ix_asset_dependency_to_entity_id ON asset_dependency (to_entity_id);
CREATE INDEX ix_asset_location_entity_id ON asset_location (entity_id);
CREATE INDEX ix_market_observations_effective_at ON market_observations (effective_at);
CREATE INDEX ix_market_observations_instrument ON market_observations (instrument);
CREATE INDEX ix_research_event_instrument ON research_event (instrument);
CREATE INDEX ix_research_event_known_at ON research_event (known_at);
CREATE INDEX ix_research_quote_instrument ON research_quote (instrument);
CREATE INDEX ix_investigation_entry_case_id ON investigation_entry (case_id);
CREATE INDEX ix_investigation_entry_kind ON investigation_entry (kind);
CREATE INDEX ix_investigation_task_assignee ON investigation_task (assignee);
CREATE INDEX ix_investigation_task_case_id ON investigation_task (case_id);
CREATE INDEX ix_investigation_task_due_at ON investigation_task (due_at);
CREATE INDEX ix_investigation_task_status ON investigation_task (status);
CREATE INDEX ix_lead_date_seen ON lead (event_date, last_seen_at, id);
CREATE INDEX ix_lead_event_date ON lead (event_date);
CREATE INDEX ix_lead_source_id ON lead (source_id);
CREATE INDEX ix_lead_status_date ON lead (status, event_date, last_seen_at, id);
CREATE INDEX ix_lead_topic_date ON lead (topic_name, event_date, last_seen_at, id);
CREATE INDEX ix_lead_document_content_hash ON lead_document (content_hash);
CREATE INDEX ix_lead_document_source_id ON lead_document (source_id);
CREATE INDEX ix_lead_retrieval_attempt_run_id ON lead_retrieval_attempt (run_id);
CREATE INDEX ix_lead_source_access_source_id ON lead_source_access (source_id);
CREATE INDEX ix_lead_headline_document_id ON lead_headline (document_id);
CREATE INDEX ix_lead_headline_lead_id ON lead_headline (lead_id);
CREATE INDEX ix_lead_revision_document_id ON lead_revision (document_id);
CREATE INDEX ix_lead_revision_lead_id ON lead_revision (lead_id);
COMMIT;
