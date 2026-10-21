BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('d8317b920a11');
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
	CONSTRAINT ck_dependency_dates CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(from_entity_id) REFERENCES entities (id), 
	FOREIGN KEY(to_entity_id) REFERENCES entities (id)
);
INSERT INTO "asset_dependency" VALUES('4eb27579-aae8-4fa5-adad-9c66637fe0d6','bd1ce484-ef94-450b-b5bf-8092886ae9a0','1c8ea962-7816-4600-9fa4-19fc09022826','alumina','material_supply','301dbe5c-c05b-4f07-9c98-b740f2c933f0','2026-01-01',NULL,'asserted','Fictional supply link',1,'local-curator','2026-10-21T18:32:31.640940+00:00');
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
	CONSTRAINT ck_asset_longitude CHECK (longitude BETWEEN -180 AND 180), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id)
);
INSERT INTO "asset_location" VALUES('883354dd-02de-4374-a2ad-039a696dc4b6','1c8ea962-7816-4600-9fa4-19fc09022826',60.1,6.5,'301dbe5c-c05b-4f07-9c98-b740f2c933f0','approximate',1,'local-curator','2026-10-21T18:32:31.637571+00:00');
CREATE TABLE audit (
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	actor VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	record_id VARCHAR NOT NULL, 
	detail JSON NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "audit" VALUES('78fab625-0d9e-4ddc-a7c8-c69e70a1685e','2026-10-21T18:32:31.511904+00:00','local-curator','create','1c8ea962-7816-4600-9fa4-19fc09022826','{"type": "entities"}');
INSERT INTO "audit" VALUES('62e2a8f8-ba1a-4c25-9de3-7e6e6f809d15','2026-10-21T18:32:31.518431+00:00','local-curator','create','bd1ce484-ef94-450b-b5bf-8092886ae9a0','{"type": "entities"}');
INSERT INTO "audit" VALUES('89755e0f-eadf-40d1-981a-f88cb35acc21','2026-10-21T18:32:31.522774+00:00','local-curator','create','8fb9f9c4-5795-443c-ab82-7a681dbbcb08','{"type": "entities"}');
INSERT INTO "audit" VALUES('2be557c9-9821-4db6-a282-56263f361447','2026-10-21T18:32:31.525922+00:00','local-curator','create','84afb865-c58a-4fdf-b91c-af15d1f29353','{"type": "sources"}');
INSERT INTO "audit" VALUES('d6e86d7e-35b1-4424-ba26-b4cf7beb6802','2026-10-21T18:32:31.533708+00:00','local-curator','acquire','301dbe5c-c05b-4f07-9c98-b740f2c933f0','{"type": "documents"}');
INSERT INTO "audit" VALUES('23a981ba-d1c8-4564-992c-645313bd2ea9','2026-10-21T18:32:31.538571+00:00','local-curator','observe','5ef0ea84-e2c9-4fcd-a700-52fdf9b958b9','{"type": "observations"}');
INSERT INTO "audit" VALUES('f6d9ed25-5bca-4af4-8969-c93b964915b8','2026-10-21T18:32:31.543270+00:00','local-curator','relate','923978e3-3e79-4277-b178-7adf875cd372','{"type": "relationships"}');
INSERT INTO "audit" VALUES('25daa09c-3ac7-48d3-8f69-3a060e52fab1','2026-10-21T18:32:31.546571+00:00','local-curator','create','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','{"type": "sources"}');
INSERT INTO "audit" VALUES('6e9c1536-2ad1-420d-9161-d13dd7e5b795','2026-10-21T18:32:31.547164+00:00','local-curator','access_decision','e941c78f-94f4-48b1-9fbc-e73d75616049','{"type": "source_access", "usage_scope": "leads_only", "credential_ref": "PERMUTABLE_API_KEY"}');
INSERT INTO "audit" VALUES('f3e9ac05-9fe8-482c-b9b1-8239e09a1166','2026-10-21T18:32:31.589003+00:00','local-curator','research_event','219fd065-ac41-45cd-9aea-0d39825a8e0c','{"version": "event-chain-paper-0.1.0"}');
INSERT INTO "audit" VALUES('3fea3938-3998-45b6-815e-99ff25f235d1','2026-10-21T18:32:31.610242+00:00','local-curator','lead_decision','dc02919b-47c2-5324-aa4d-7a37853bdd0d','{"status": "follow_up", "reason": "Check the operator update", "primary_document_id": null, "observation_id": null}');
INSERT INTO "audit" VALUES('b6f9df08-1863-4996-b7f4-4d716e8e5105','2026-10-21T18:32:31.613670+00:00','local-curator','lead_decision','dc02919b-47c2-5324-aa4d-7a37853bdd0d','{"status": "confirmed", "reason": "The operator update confirms the suspension", "primary_document_id": "301dbe5c-c05b-4f07-9c98-b740f2c933f0", "observation_id": "5ef0ea84-e2c9-4fcd-a700-52fdf9b958b9"}');
INSERT INTO "audit" VALUES('a07b3cb4-f858-45d9-8143-35b3e815ff56','2026-10-21T18:32:31.616772+00:00','local-curator','paper_policy','d4a1ce0a-e065-47f5-a7ac-ac0926081605','{"version": "event-chain-paper-0.1.0"}');
INSERT INTO "audit" VALUES('2bcca667-d444-45c9-ba20-1a6ad30add8b','2026-10-21T18:32:31.620162+00:00','local-curator','research_event','1f857e31-0a5d-420c-9714-020018d25930','{"version": "event-chain-paper-0.1.0"}');
INSERT INTO "audit" VALUES('bc859d9c-ecfa-458b-90a2-796f105c1800','2026-10-21T18:32:31.623493+00:00','local-curator','research_event','1750baca-a24d-4766-91ae-996a2e5f521e','{"version": "event-chain-paper-0.1.0"}');
INSERT INTO "audit" VALUES('a58900a8-98d3-40a5-badf-1890fde735e8','2026-10-21T18:32:31.626645+00:00','local-curator','investigation_created','329d71af-7461-4943-8385-bc4de5c6566d','{"type": "investigation"}');
INSERT INTO "audit" VALUES('9aad0fdc-132b-4bc4-ba13-40f19ce1ff1b','2026-10-21T18:32:31.631646+00:00','local-curator','investigation_revised','329d71af-7461-4943-8385-bc4de5c6566d','{"type": "investigation"}');
INSERT INTO "audit" VALUES('3f583d7f-6e37-4a83-8d05-986b6c7b2370','2026-10-21T18:32:31.634993+00:00','local-curator','investigation_revised','329d71af-7461-4943-8385-bc4de5c6566d','{"type": "investigation"}');
INSERT INTO "audit" VALUES('8018fd56-3e41-4f55-86f7-c560dfa08a82','2026-10-21T18:32:31.637827+00:00','local-curator','asset_location','883354dd-02de-4374-a2ad-039a696dc4b6','{"type": "asset_location"}');
INSERT INTO "audit" VALUES('8a87e4a1-3075-4acc-9618-19aacdc519f1','2026-10-21T18:32:31.641296+00:00','local-curator','asset_dependency','4eb27579-aae8-4fa5-adad-9c66637fe0d6','{"type": "asset_dependency"}');
CREATE TABLE candidate (
	id VARCHAR NOT NULL, 
	build_id VARCHAR NOT NULL, 
	raw_name VARCHAR NOT NULL, 
	country VARCHAR(2), 
	reported_value VARCHAR NOT NULL, 
	unit VARCHAR NOT NULL, 
	evidence_reference VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	entity_id VARCHAR, 
	observation_id VARCHAR, 
	review_id VARCHAR, 
	findings JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(build_id) REFERENCES evidence_build (id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id), 
	FOREIGN KEY(observation_id) REFERENCES observations (id), 
	FOREIGN KEY(review_id) REFERENCES reviews (id)
);
CREATE TABLE commodity (
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (code)
);
INSERT INTO "commodity" VALUES('aluminium','Aluminium');
INSERT INTO "commodity" VALUES('alumina','Alumina');
INSERT INTO "commodity" VALUES('bauxite','Bauxite');
CREATE TABLE company (
	entity_id VARCHAR NOT NULL, 
	PRIMARY KEY (entity_id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id)
);
INSERT INTO "company" VALUES('8fb9f9c4-5795-443c-ab82-7a681dbbcb08');
CREATE TABLE "company_facility_relationship" (
	relationship_id VARCHAR NOT NULL, 
	company_id VARCHAR NOT NULL, 
	facility_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	evidence_reference TEXT NOT NULL, 
	percentage VARCHAR(40), 
	valid_from DATE NOT NULL, 
	valid_to DATE, 
	PRIMARY KEY (relationship_id), 
	CONSTRAINT ck_relationship_interval CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	CONSTRAINT ck_relationship_role CHECK (role IN ('OWNS','OPERATES')), 
	CONSTRAINT ck_relationship_share CHECK (percentage IS NULL OR (CAST(percentage AS NUMERIC) >= 0 AND CAST(percentage AS NUMERIC) <= 100)), 
	FOREIGN KEY(relationship_id) REFERENCES relationships (id), 
	FOREIGN KEY(document_id) REFERENCES document_version (document_id), 
	FOREIGN KEY(company_id) REFERENCES company (entity_id), 
	FOREIGN KEY(facility_id) REFERENCES facility (entity_id)
);
INSERT INTO "company_facility_relationship" VALUES('923978e3-3e79-4277-b178-7adf875cd372','8fb9f9c4-5795-443c-ab82-7a681dbbcb08','1c8ea962-7816-4600-9fa4-19fc09022826','301dbe5c-c05b-4f07-9c98-b740f2c933f0','OWNS','Operations update, owner line','100','2020-01-01',NULL);
CREATE TABLE country (
	code VARCHAR(2) NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (code)
);
INSERT INTO "country" VALUES('AU','Australia');
INSERT INTO "country" VALUES('NO','Norway');
INSERT INTO "country" VALUES('IS','Iceland');
INSERT INTO "country" VALUES('CA','Canada');
INSERT INTO "country" VALUES('US','United States');
INSERT INTO "country" VALUES('BR','Brazil');
INSERT INTO "country" VALUES('QA','Qatar');
INSERT INTO "country" VALUES('SK','Slovakia');
INSERT INTO "country" VALUES('DE','Germany');
INSERT INTO "country" VALUES('FR','France');
INSERT INTO "country" VALUES('IN','India');
INSERT INTO "country" VALUES('CN','China');
INSERT INTO "country" VALUES('RU','Russia');
INSERT INTO "country" VALUES('AE','United Arab Emirates');
INSERT INTO "country" VALUES('BH','Bahrain');
INSERT INTO "country" VALUES('NZ','New Zealand');
INSERT INTO "country" VALUES('GB','United Kingdom');
INSERT INTO "country" VALUES('ZA','South Africa');
INSERT INTO "country" VALUES('JM','Jamaica');
INSERT INTO "country" VALUES('GN','Guinea');
INSERT INTO "country" VALUES('IE','Ireland');
INSERT INTO "country" VALUES('ES','Spain');
INSERT INTO "country" VALUES('GR','Greece');
INSERT INTO "country" VALUES('MZ','Mozambique');
INSERT INTO "country" VALUES('ID','Indonesia');
INSERT INTO "country" VALUES('MY','Malaysia');
INSERT INTO "country" VALUES('OM','Oman');
INSERT INTO "country" VALUES('SA','Saudi Arabia');
CREATE TABLE document_version (
	document_id VARCHAR NOT NULL, 
	snapshot_hash VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (document_id), 
	CONSTRAINT ck_document_version_positive CHECK (version > 0), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(snapshot_hash) REFERENCES source_snapshot (content_hash)
);
INSERT INTO "document_version" VALUES('301dbe5c-c05b-4f07-9c98-b740f2c933f0','944cab31fc41a5e5ec42f7f67385748c4f7f9d3eed0078f7a932bd9ab872970a',1);
INSERT INTO "document_version" VALUES('c26d275a-4451-440d-8cc3-13240787750e','3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393',1);
INSERT INTO "document_version" VALUES('f1d28eaf-2662-4f26-b6bf-decab92d660f','81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9',1);
INSERT INTO "document_version" VALUES('48f95ac7-3e0f-48f4-ad20-b11f0b16c074','a80cebad73e416c3c5749785fe0fec05197c16ef7607ef48c4dd638dbeb62b06',1);
CREATE TABLE documents (
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
	FOREIGN KEY(source_id) REFERENCES sources (id), 
	UNIQUE (source_id, original_url, content_hash), 
	UNIQUE (source_id, original_url, version)
);
INSERT INTO "documents" VALUES('301dbe5c-c05b-4f07-9c98-b740f2c933f0','84afb865-c58a-4fdf-b91c-af15d1f29353','Operations update','https://fjord.example/update','2026-10-08','2026-10-21T18:32:31.532629+00:00','text/plain','944cab31fc41a5e5ec42f7f67385748c4f7f9d3eed0078f7a932bd9ab872970a',1);
INSERT INTO "documents" VALUES('c26d275a-4451-440d-8cc3-13240787750e','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','Permutable events historical ALI_COM page 1','https://copilot-api.permutable.ai/v1/events/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01',NULL,'2026-10-21T18:32:31.553256+00:00','application/json','3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393',1);
INSERT INTO "documents" VALUES('f1d28eaf-2662-4f26-b6bf-decab92d660f','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','Permutable event_headlines historical ALI_COM page 1','https://copilot-api.permutable.ai/v1/event_headlines/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01',NULL,'2026-10-21T18:32:31.594617+00:00','application/json','81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9',1);
INSERT INTO "documents" VALUES('48f95ac7-3e0f-48f4-ad20-b11f0b16c074','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','Permutable ticker_info live ALI_COM','https://copilot-api.permutable.ai/v1/ticker/ALI_COM/info',NULL,'2026-10-21T18:32:31.602686+00:00','application/json','a80cebad73e416c3c5749785fe0fec05197c16ef7607ef48c4dd638dbeb62b06',1);
CREATE TABLE entities (
	id VARCHAR NOT NULL, 
	name VARCHAR(256) NOT NULL, 
	kind VARCHAR NOT NULL, 
	facility_type VARCHAR, 
	country VARCHAR(2), 
	region VARCHAR, 
	commodity VARCHAR NOT NULL, 
	aliases JSON NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('company','facility'))
);
INSERT INTO "entities" VALUES('1c8ea962-7816-4600-9fa4-19fc09022826','Fjord Aluminium Works','facility','smelter','NO','','aluminium','["Fjord Works"]');
INSERT INTO "entities" VALUES('bd1ce484-ef94-450b-b5bf-8092886ae9a0','Fjord Alumina Refinery','facility','refinery','NO','','aluminium','[]');
INSERT INTO "entities" VALUES('8fb9f9c4-5795-443c-ab82-7a681dbbcb08','Fjord Metals ASA','company',NULL,'NO','','aluminium','[]');
CREATE TABLE entity_alias (
	id VARCHAR NOT NULL, 
	entity_id VARCHAR NOT NULL, 
	name VARCHAR(256) NOT NULL, 
	normalized_name VARCHAR(256) NOT NULL, 
	actor VARCHAR NOT NULL, 
	reason TEXT NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id), 
	UNIQUE (entity_id, normalized_name)
);
INSERT INTO "entity_alias" VALUES('97343921-b7fb-4c0d-9fe0-bd8006d4cc0f','1c8ea962-7816-4600-9fa4-19fc09022826','Fjord Works','fjord works','local-curator','Initial curated alias','2026-10-21T18:32:31.511487+00:00');
CREATE TABLE entity_evidence (
	entity_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	evidence_reference TEXT NOT NULL, 
	reviewer VARCHAR NOT NULL, 
	reason TEXT NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (entity_id, document_id), 
	FOREIGN KEY(document_id) REFERENCES document_version (document_id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id)
);
CREATE TABLE entity_supersession (
	old_entity_id VARCHAR NOT NULL, 
	new_entity_id VARCHAR NOT NULL, 
	actor VARCHAR NOT NULL, 
	reason TEXT NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (old_entity_id), 
	CONSTRAINT ck_supersession_distinct CHECK (old_entity_id <> new_entity_id), 
	FOREIGN KEY(new_entity_id) REFERENCES entities (id), 
	FOREIGN KEY(old_entity_id) REFERENCES entities (id)
);
CREATE TABLE evidence_build (
	id VARCHAR(64) NOT NULL, 
	document_id VARCHAR NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	parser_version VARCHAR NOT NULL, 
	pipeline_version VARCHAR NOT NULL, 
	specification JSON NOT NULL, 
	logical_output JSON NOT NULL, 
	output_hash VARCHAR(64) NOT NULL, 
	actor VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);
CREATE TABLE facility (
	entity_id VARCHAR NOT NULL, 
	type_code VARCHAR NOT NULL, 
	country_code VARCHAR(2) NOT NULL, 
	region_id VARCHAR, 
	commodity_code VARCHAR NOT NULL, 
	PRIMARY KEY (entity_id), 
	FOREIGN KEY(commodity_code) REFERENCES commodity (code), 
	FOREIGN KEY(country_code) REFERENCES country (code), 
	FOREIGN KEY(entity_id) REFERENCES entities (id), 
	FOREIGN KEY(region_id) REFERENCES region (id), 
	FOREIGN KEY(type_code) REFERENCES facility_type (code)
);
INSERT INTO "facility" VALUES('1c8ea962-7816-4600-9fa4-19fc09022826','smelter','NO',NULL,'aluminium');
INSERT INTO "facility" VALUES('bd1ce484-ef94-450b-b5bf-8092886ae9a0','refinery','NO',NULL,'aluminium');
CREATE TABLE facility_type (
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (code)
);
INSERT INTO "facility_type" VALUES('smelter','Primary aluminium smelter');
INSERT INTO "facility_type" VALUES('refinery','Alumina refinery');
INSERT INTO "facility_type" VALUES('bauxite_mine','Bauxite mine');
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
INSERT INTO "investigation" VALUES('329d71af-7461-4943-8385-bc4de5c6566d','Fjord curtailment','investigating',3,'{"title": "Fjord curtailment", "summary": "", "owner": "", "region": "", "asset_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "review_at": null, "status": "investigating", "entries": [{"kind": "evidence", "text": "Operator update", "document_id": "301dbe5c-c05b-4f07-9c98-b740f2c933f0", "source_url": null, "stance": "context", "hypothesis_id": null, "passage": "", "published_at": null, "id": "4b512f12-f923-4837-ad9b-cb8caa95a4be", "actor": "local-curator", "recorded_at": "2026-10-21T18:32:31.629438+00:00"}, {"kind": "note", "text": "Vendor event", "document_id": "c26d275a-4451-440d-8cc3-13240787750e", "source_url": null, "stance": "context", "hypothesis_id": null, "passage": "", "published_at": null, "id": "043849ce-efb9-4c2a-a196-ea7d7aa269c5", "actor": "local-curator", "recorded_at": "2026-10-21T18:32:31.634053+00:00"}], "tasks": []}','2026-10-21T18:32:31.626040+00:00','2026-10-21T18:32:31.634097+00:00');
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
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(hypothesis_id) REFERENCES investigation_entry (id)
);
INSERT INTO "investigation_entry" VALUES('4b512f12-f923-4837-ad9b-cb8caa95a4be','329d71af-7461-4943-8385-bc4de5c6566d','evidence','Operator update','301dbe5c-c05b-4f07-9c98-b740f2c933f0',NULL,'context',NULL,'',NULL,'local-curator','2026-10-21T18:32:31.629438+00:00');
INSERT INTO "investigation_entry" VALUES('043849ce-efb9-4c2a-a196-ea7d7aa269c5','329d71af-7461-4943-8385-bc4de5c6566d','note','Vendor event','c26d275a-4451-440d-8cc3-13240787750e',NULL,'context',NULL,'',NULL,'local-curator','2026-10-21T18:32:31.634053+00:00');
CREATE TABLE investigation_revision (
	id VARCHAR NOT NULL, 
	case_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	actor VARCHAR NOT NULL, 
	snapshot JSON NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_investigation_version UNIQUE (case_id, version), 
	FOREIGN KEY(case_id) REFERENCES investigation (id)
);
INSERT INTO "investigation_revision" VALUES('270ab8d7-0c32-43f4-8b9e-c03cebea2cc3','329d71af-7461-4943-8385-bc4de5c6566d',1,'local-curator','{"title": "Fjord curtailment", "summary": "", "owner": "", "region": "", "asset_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "review_at": null, "status": "investigating", "entries": [], "tasks": []}','2026-10-21T18:32:31.626465+00:00');
INSERT INTO "investigation_revision" VALUES('50e7f929-2bfd-4d1f-8977-4f6515c3c18b','329d71af-7461-4943-8385-bc4de5c6566d',2,'local-curator','{"title": "Fjord curtailment", "summary": "", "owner": "", "region": "", "asset_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "review_at": null, "status": "investigating", "entries": [{"kind": "evidence", "text": "Operator update", "document_id": "301dbe5c-c05b-4f07-9c98-b740f2c933f0", "source_url": null, "stance": "context", "hypothesis_id": null, "passage": "", "published_at": null, "id": "4b512f12-f923-4837-ad9b-cb8caa95a4be", "actor": "local-curator", "recorded_at": "2026-10-21T18:32:31.629438+00:00"}], "tasks": []}','2026-10-21T18:32:31.630316+00:00');
INSERT INTO "investigation_revision" VALUES('1dadb1b7-b35f-46c9-9540-6a1b9c7a1790','329d71af-7461-4943-8385-bc4de5c6566d',3,'local-curator','{"title": "Fjord curtailment", "summary": "", "owner": "", "region": "", "asset_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "review_at": null, "status": "investigating", "entries": [{"kind": "evidence", "text": "Operator update", "document_id": "301dbe5c-c05b-4f07-9c98-b740f2c933f0", "source_url": null, "stance": "context", "hypothesis_id": null, "passage": "", "published_at": null, "id": "4b512f12-f923-4837-ad9b-cb8caa95a4be", "actor": "local-curator", "recorded_at": "2026-10-21T18:32:31.629438+00:00"}, {"kind": "note", "text": "Vendor event", "document_id": "c26d275a-4451-440d-8cc3-13240787750e", "source_url": null, "stance": "context", "hypothesis_id": null, "passage": "", "published_at": null, "id": "043849ce-efb9-4c2a-a196-ea7d7aa269c5", "actor": "local-curator", "recorded_at": "2026-10-21T18:32:31.634053+00:00"}], "tasks": []}','2026-10-21T18:32:31.634477+00:00');
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
	FOREIGN KEY(task_id) REFERENCES investigation_task (id), 
	FOREIGN KEY(entry_id) REFERENCES investigation_entry (id)
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
	observation_id VARCHAR, search_text TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_lead_status CHECK (status IN ('new','follow_up','dismissed','confirmed')), 
	CONSTRAINT ck_lead_confirmed_evidence CHECK (status <> 'confirmed' OR primary_document_id IS NOT NULL), 
	FOREIGN KEY(observation_id) REFERENCES observations (id), 
	FOREIGN KEY(primary_document_id) REFERENCES documents (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id), 
	CONSTRAINT uq_lead_source_external UNIQUE (source_id, external_id)
);
INSERT INTO "lead" VALUES('dc02919b-47c2-5324-aa4d-7a37853bdd0d','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','fixture-event-1','ALI_COM','confirmed','2026-10-21T18:32:31.553256+00:00','2026-10-21T18:32:31.594617+00:00','2026-10-09T06:00:00','Supply-Other','2026-10-09T08:00:00','a08d3d5556650e69e81204ef234179d26a0185fcb68dba487b9f121328b65153',1,'local-curator','The operator update confirms the suspension','2026-10-21T18:32:31.613227+00:00','301dbe5c-c05b-4f07-9c98-b740f2c933f0','5ef0ea84-e2c9-4fcd-a700-52fdf9b958b9','');
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
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(lead_id) REFERENCES lead (id), 
	CONSTRAINT uq_lead_headline_content UNIQUE (lead_id, content_hash)
);
INSERT INTO "lead_headline" VALUES('3b420e84-3590-5c9f-b38b-66422793a225','dc02919b-47c2-5324-aa4d-7a37853bdd0d','f1d28eaf-2662-4f26-b6bf-decab92d660f','413425c53b2e8d5aa37be180988742dd4e3e71955975592a3b7432036db7f777','permutable-leads-1.0.0','Fjord Works curtails potline','Example News','https://news.example/fjord','2026-10-09T06:10:00','en','2026-10-21T18:32:31.597146+00:00');
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
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(lead_id) REFERENCES lead (id), 
	CONSTRAINT uq_lead_revision_content UNIQUE (lead_id, content_hash)
);
INSERT INTO "lead_revision" VALUES('c23a8266-7cf9-59c3-8048-b96072b2fd6a','dc02919b-47c2-5324-aa4d-7a37853bdd0d','c26d275a-4451-440d-8cc3-13240787750e','a08d3d5556650e69e81204ef234179d26a0185fcb68dba487b9f121328b65153','permutable-leads-1.0.0','Fictional smelter curtailment','2026-10-09T06:00:00','Fjord Works curtails a potline after a power outage','Supply-Other','Asset','2026-10-09T08:00:00','["1c8ea962-7816-4600-9fa4-19fc09022826"]','2026-10-21T18:32:31.558918+00:00');
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
	CHECK (volume IS NULL OR volume >= 0), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);
CREATE TABLE observation_detail (
	observation_id VARCHAR NOT NULL, 
	normalized_value VARCHAR(40), 
	normalized_unit VARCHAR, 
	valid_from DATE NOT NULL, 
	valid_to DATE, 
	PRIMARY KEY (observation_id), 
	CONSTRAINT ck_detail_unit CHECK (normalized_unit IS NULL OR normalized_unit IN ('t/year','MW','percentage')), 
	CONSTRAINT ck_detail_nonnegative CHECK (normalized_value IS NULL OR normalized_value >= 0), 
	CONSTRAINT ck_detail_interval CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	FOREIGN KEY(observation_id) REFERENCES observations (id)
);
INSERT INTO "observation_detail" VALUES('5ef0ea84-e2c9-4fcd-a700-52fdf9b958b9',NULL,NULL,'2026-10-08',NULL);
CREATE TABLE "observations" (
	id VARCHAR NOT NULL, 
	entity_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	attribute VARCHAR NOT NULL, 
	reported_value VARCHAR NOT NULL, 
	reported_unit VARCHAR NOT NULL, 
	normalized_value FLOAT, 
	normalized_unit VARCHAR, 
	valid_from VARCHAR NOT NULL, 
	valid_to VARCHAR, 
	evidence_reference VARCHAR NOT NULL, 
	quality_status VARCHAR NOT NULL, 
	quality_messages JSON NOT NULL, 
	recorded_at VARCHAR NOT NULL, 
	parser_version VARCHAR DEFAULT 'manual-v1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_observation_interval CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	CONSTRAINT ck_observation_nonnegative CHECK (normalized_value IS NULL OR normalized_value >= 0), 
	CONSTRAINT ck_observation_dimension CHECK ((attribute='capacity' AND reported_unit IN ('t/year','kt/year','Mt/year')) OR (attribute='power' AND reported_unit='MW') OR (attribute='ownership_percentage' AND reported_unit='percentage') OR (attribute='status' AND reported_unit='status')), 
	FOREIGN KEY(entity_id) REFERENCES entities (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);
INSERT INTO "observations" VALUES('5ef0ea84-e2c9-4fcd-a700-52fdf9b958b9','1c8ea962-7816-4600-9fa4-19fc09022826','301dbe5c-c05b-4f07-9c98-b740f2c933f0','status','suspended','status',NULL,NULL,'2026-10-08',NULL,'Operations update, sentence 1','PASS','[]','2026-10-21T18:32:31.537817+00:00','manual-v1');
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
INSERT INTO "paper_policy" VALUES('d4a1ce0a-e065-47f5-a7ac-ac0926081605','{"enabled": false, "instrument": "ALUMINIUM_DEMO", "min_cases": 5, "min_similarity": 0.65, "edge_threshold_bps": 50, "min_agreement": 0.8, "max_trade_notional": "1000", "max_exposure_fraction": "0.2", "max_drawdown_fraction": "0.1", "fee_bps": 5, "slippage_bps": 5, "cooldown_seconds": 3600, "max_daily_trades": 5, "max_quote_age_seconds": 300, "max_event_age_seconds": 3600}','local-curator','2026-10-21T18:32:31.616444+00:00');
CREATE TABLE region (
	id VARCHAR NOT NULL, 
	country_code VARCHAR(2) NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(country_code) REFERENCES country (code), 
	UNIQUE (country_code, name)
);
CREATE TABLE relationships (
	id VARCHAR NOT NULL, 
	company_id VARCHAR NOT NULL, 
	facility_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	percentage FLOAT, 
	valid_from VARCHAR NOT NULL, 
	valid_to VARCHAR, 
	document_id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('OWNS','OPERATES')), 
	CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 100)), 
	CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	FOREIGN KEY(company_id) REFERENCES entities (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(facility_id) REFERENCES entities (id)
);
INSERT INTO "relationships" VALUES('923978e3-3e79-4277-b178-7adf875cd372','8fb9f9c4-5795-443c-ab82-7a681dbbcb08','1c8ea962-7816-4600-9fa4-19fc09022826','OWNS',100.0,'2020-01-01',NULL,'301dbe5c-c05b-4f07-9c98-b740f2c933f0');
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
INSERT INTO "research_event" VALUES('219fd065-ac41-45cd-9aea-0d39825a8e0c','lead:dc02919b-47c2-5324-aa4d-7a37853bdd0d:a08d3d5556650e69e81204ef234179d26a0185fcb68dba487b9f121328b65153','ALUMINIUM_DEMO','energy','2026-10-09T06:00:00+00:00','2026-10-21T18:32:31.558918+00:00','2026-10-21T18:32:31.588571+00:00',1,'{"occurred_at": "2026-10-09T06:00:00+00:00", "known_at": "2026-10-21T18:32:31.558918+00:00", "historical": true, "external_key": "lead:dc02919b-47c2-5324-aa4d-7a37853bdd0d:a08d3d5556650e69e81204ef234179d26a0185fcb68dba487b9f121328b65153", "instrument": "ALUMINIUM_DEMO", "kind": "energy", "title": "Fictional smelter curtailment", "summary": "Fjord Works curtails a potline after a power outage", "source_reference": "document:c26d275a-4451-440d-8cc3-13240787750e", "entity_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "countries": [], "tags": ["ali_com", "supply-other"], "lead_id": "dc02919b-47c2-5324-aa4d-7a37853bdd0d"}','{"version": "event-chain-paper-0.1.0", "window_hours": 72, "event_ids": ["219fd065-ac41-45cd-9aea-0d39825a8e0c"], "sequence": ["energy"], "edges": []}','{"kind:energy": 3, "tag:ali_com": 2, "tag:supply-other": 2, "word:power": 1, "word:curtailment": 1, "word:fictional": 1, "word:works": 1, "word:outage": 1, "word:potline": 1, "word:after": 1, "word:smelter": 1, "word:curtails": 1, "word:fjord": 1}');
INSERT INTO "research_event" VALUES('1f857e31-0a5d-420c-9714-020018d25930','fixture-owner-news','ALUMINIUM_DEMO','corporate','2026-10-21T18:22:31.618362+00:00','2026-10-21T18:22:31.618362+00:00','2026-10-21T18:32:31.619906+00:00',1,'{"occurred_at": "2026-10-21T18:22:31.618362+00:00", "known_at": "2026-10-21T18:22:31.618362+00:00", "historical": true, "external_key": "fixture-owner-news", "instrument": "ALUMINIUM_DEMO", "kind": "corporate", "title": "Owner news", "summary": "Fictional", "source_reference": "synthetic:fixture", "entity_ids": ["8fb9f9c4-5795-443c-ab82-7a681dbbcb08"], "countries": [], "tags": [], "lead_id": null}','{"version": "event-chain-paper-0.1.0", "window_hours": 72, "event_ids": ["1f857e31-0a5d-420c-9714-020018d25930"], "sequence": ["corporate"], "edges": []}','{"kind:corporate": 3, "word:fictional": 1, "word:owner": 1, "word:news": 1}');
INSERT INTO "research_event" VALUES('1750baca-a24d-4766-91ae-996a2e5f521e','fixture-plant-outage','ALUMINIUM_DEMO','supply','2026-10-21T18:27:31.618362+00:00','2026-10-21T18:32:31.618362+00:00','2026-10-21T18:32:31.623201+00:00',1,'{"occurred_at": "2026-10-21T18:27:31.618362+00:00", "known_at": "2026-10-21T18:32:31.618362+00:00", "historical": true, "external_key": "fixture-plant-outage", "instrument": "ALUMINIUM_DEMO", "kind": "supply", "title": "Plant outage", "summary": "Fictional", "source_reference": "synthetic:fixture", "entity_ids": ["1c8ea962-7816-4600-9fa4-19fc09022826"], "countries": [], "tags": [], "lead_id": null}','{"version": "event-chain-paper-0.1.0", "window_hours": 72, "event_ids": ["1f857e31-0a5d-420c-9714-020018d25930", "1750baca-a24d-4766-91ae-996a2e5f521e"], "sequence": ["corporate", "supply"], "edges": [{"from": "1f857e31-0a5d-420c-9714-020018d25930", "to": "1750baca-a24d-4766-91ae-996a2e5f521e", "reasons": ["registered_relationship"], "causal": false}]}','{"kind:corporate": 3, "word:fictional": 2, "word:owner": 1, "word:news": 1, "kind:supply": 3, "word:plant": 1, "word:outage": 1, "transition:corporate>supply": 4}');
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
INSERT INTO "research_paper_account" VALUES('paper','d4a1ce0a-e065-47f5-a7ac-ac0926081605','ALUMINIUM_DEMO','100000','0','100000',0);
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
CREATE TABLE retrieval_attempt (
	id VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	url VARCHAR NOT NULL, 
	attempt INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	error VARCHAR, 
	http_status INTEGER, 
	recorded_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_id) REFERENCES runs (id)
);
INSERT INTO "retrieval_attempt" VALUES('4c1eb2f7-3587-41dd-bce3-355c2d681b3d','971a3e47-37f2-4ff4-95bb-7a1cdf4e7840','https://copilot-api.permutable.ai/v1/events/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01',1,'success',NULL,200,'2026-10-21T18:32:31.551591+00:00');
INSERT INTO "retrieval_attempt" VALUES('a839cc70-324c-4b71-b778-8f9551b6cdab','8cd7b3ff-fa80-4947-84b7-cd4f898e6c8b','https://copilot-api.permutable.ai/v1/event_headlines/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01',1,'success',NULL,200,'2026-10-21T18:32:31.593288+00:00');
INSERT INTO "retrieval_attempt" VALUES('21a7743b-2de2-497c-a761-73e34a9bfbb5','de5c5f54-509b-489c-bda1-8d866b60c54e','https://copilot-api.permutable.ai/v1/ticker/ALI_COM/info',1,'success',NULL,200,'2026-10-21T18:32:31.601411+00:00');
CREATE TABLE reviews (
	id VARCHAR NOT NULL, 
	raw_name VARCHAR NOT NULL, 
	candidate_ids JSON NOT NULL, 
	status VARCHAR NOT NULL, 
	selected_entity_id VARCHAR, 
	reviewer VARCHAR, 
	reason TEXT, 
	decided_at VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(selected_entity_id) REFERENCES entities (id)
);
CREATE TABLE runs (
	id VARCHAR NOT NULL, 
	started_at VARCHAR NOT NULL, 
	pipeline_version VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	manifest JSON NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "runs" VALUES('ecee6f99-2ab4-43fc-900f-c8d534144a90','2026-10-21T18:32:31.533532+00:00','1.0.0','success','{"content_hash": "944cab31fc41a5e5ec42f7f67385748c4f7f9d3eed0078f7a932bd9ab872970a", "document_id": "301dbe5c-c05b-4f07-9c98-b740f2c933f0", "adapter": "text-upload-v1"}');
INSERT INTO "runs" VALUES('971a3e47-37f2-4ff4-95bb-7a1cdf4e7840','2026-10-21T18:32:31.550039+00:00','1.0.0','success','{"source_id": "a2aa0e92-c63f-5207-a962-24e5b9d1e4c5", "url": "https://copilot-api.permutable.ai/v1/events/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01", "adapter": "permutable-api-v1", "actor": "local-curator", "credential_ref": "PERMUTABLE_API_KEY", "document_id": "c26d275a-4451-440d-8cc3-13240787750e", "content_hash": "3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393", "final_url": "https://copilot-api.permutable.ai/v1/events/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01", "access_decision_id": "e941c78f-94f4-48b1-9fbc-e73d75616049"}');
INSERT INTO "runs" VALUES('a43c0bbb-f809-4011-8a62-b2eeaaf8a38d','2026-10-21T18:32:31.559126+00:00','1.0.0','success','{"adapter": "permutable-leads", "parser_version": "permutable-leads-1.0.0", "document_id": "c26d275a-4451-440d-8cc3-13240787750e", "content_hash": "3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393", "feed": "events", "ticker": "ALI_COM", "leads_created": 1, "revisions_added": 1, "headlines_added": 0}');
INSERT INTO "runs" VALUES('8cd7b3ff-fa80-4947-84b7-cd4f898e6c8b','2026-10-21T18:32:31.592372+00:00','1.0.0','success','{"source_id": "a2aa0e92-c63f-5207-a962-24e5b9d1e4c5", "url": "https://copilot-api.permutable.ai/v1/event_headlines/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01", "adapter": "permutable-api-v1", "actor": "local-curator", "credential_ref": "PERMUTABLE_API_KEY", "document_id": "f1d28eaf-2662-4f26-b6bf-decab92d660f", "content_hash": "81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9", "final_url": "https://copilot-api.permutable.ai/v1/event_headlines/feed/historical/ticker/ALI_COM?event_type=Asset&limit=500&start_date=2026-10-01", "access_decision_id": "e941c78f-94f4-48b1-9fbc-e73d75616049"}');
INSERT INTO "runs" VALUES('16df7052-fd19-4151-bd9b-882cb862709c','2026-10-21T18:32:31.597354+00:00','1.0.0','success','{"adapter": "permutable-leads", "parser_version": "permutable-leads-1.0.0", "document_id": "f1d28eaf-2662-4f26-b6bf-decab92d660f", "content_hash": "81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9", "feed": "event_headlines", "ticker": "ALI_COM", "leads_created": 0, "revisions_added": 0, "headlines_added": 1}');
INSERT INTO "runs" VALUES('de5c5f54-509b-489c-bda1-8d866b60c54e','2026-10-21T18:32:31.600387+00:00','1.0.0','success','{"source_id": "a2aa0e92-c63f-5207-a962-24e5b9d1e4c5", "url": "https://copilot-api.permutable.ai/v1/ticker/ALI_COM/info", "adapter": "permutable-api-v1", "actor": "local-curator", "credential_ref": "PERMUTABLE_API_KEY", "document_id": "48f95ac7-3e0f-48f4-ad20-b11f0b16c074", "content_hash": "a80cebad73e416c3c5749785fe0fec05197c16ef7607ef48c4dd638dbeb62b06", "final_url": "https://copilot-api.permutable.ai/v1/ticker/ALI_COM/info", "access_decision_id": "e941c78f-94f4-48b1-9fbc-e73d75616049"}');
CREATE TABLE "source_access" (
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
	usage_scope VARCHAR DEFAULT 'evidence' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_source_access_status CHECK (status IN ('permitted','review_required','restricted')), 
	CONSTRAINT ck_source_access_usage CHECK (usage_scope IN ('evidence','leads_only')), 
	CONSTRAINT ck_source_access_credential CHECK ((credential_ref IS NULL) = (auth_header IS NULL)), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
);
INSERT INTO "source_access" VALUES('e941c78f-94f4-48b1-9fbc-e73d75616049','a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','permitted','["copilot-api.permutable.ai"]','Commercial Permutable AI licence held by MuniQuant; factual event and headline feeds used as curator leads','Raw API responses retained locally as fingerprinted snapshots; not redistributed and never exported as evidence','local-curator','2026-10-21T18:32:31.546971+00:00','PERMUTABLE_API_KEY','x-api-key','leads_only');
CREATE TABLE source_document_relation (
	source_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	PRIMARY KEY (source_id, document_id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
);
INSERT INTO "source_document_relation" VALUES('84afb865-c58a-4fdf-b91c-af15d1f29353','301dbe5c-c05b-4f07-9c98-b740f2c933f0');
INSERT INTO "source_document_relation" VALUES('a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','c26d275a-4451-440d-8cc3-13240787750e');
INSERT INTO "source_document_relation" VALUES('a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','f1d28eaf-2662-4f26-b6bf-decab92d660f');
INSERT INTO "source_document_relation" VALUES('a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','48f95ac7-3e0f-48f4-ad20-b11f0b16c074');
CREATE TABLE source_snapshot (
	content_hash VARCHAR(64) NOT NULL, 
	storage_reference VARCHAR NOT NULL, 
	byte_size INTEGER, 
	PRIMARY KEY (content_hash), 
	CONSTRAINT ck_snapshot_size CHECK (byte_size >= 0)
);
INSERT INTO "source_snapshot" VALUES('944cab31fc41a5e5ec42f7f67385748c4f7f9d3eed0078f7a932bd9ab872970a','944cab31fc41a5e5ec42f7f67385748c4f7f9d3eed0078f7a932bd9ab872970a',65);
INSERT INTO "source_snapshot" VALUES('3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393','3b0bce23dee2abda1fe4131dea0154546a7bbbe4a6561f9e381c897dc5033393',337);
INSERT INTO "source_snapshot" VALUES('81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9','81762263837274595c2726ff49ded8c43ae46f6e4a8230ee6f7132adbe0289f9',207);
INSERT INTO "source_snapshot" VALUES('a80cebad73e416c3c5749785fe0fec05197c16ef7607ef48c4dd638dbeb62b06','a80cebad73e416c3c5749785fe0fec05197c16ef7607ef48c4dd638dbeb62b06',60);
CREATE TABLE sources (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	publisher VARCHAR NOT NULL, 
	source_type VARCHAR NOT NULL, 
	url VARCHAR NOT NULL, 
	access_status VARCHAR NOT NULL, 
	notes TEXT NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "sources" VALUES('84afb865-c58a-4fdf-b91c-af15d1f29353','Fjord Metals releases','Fjord Metals ASA (fictional)','synthetic','https://fjord.example/','permitted','');
INSERT INTO "sources" VALUES('a2aa0e92-c63f-5207-a962-24e5b9d1e4c5','Permutable AI licensed event feed','Permutable AI','commercial','https://copilot-api.permutable.ai/v1','permitted','Licensed commercial event and headline data. Lead-only: points curators to industrial changes and is never cited as observation evidence. Vendor sentiment, impact and signal fields are not ingested.');
CREATE INDEX ix_documents_content_hash ON documents (content_hash);
CREATE INDEX ix_documents_source_id ON documents (source_id);
CREATE INDEX ix_market_observations_effective_at ON market_observations (effective_at);
CREATE INDEX ix_market_observations_instrument ON market_observations (instrument);
CREATE INDEX ix_entity_alias_entity_id ON entity_alias (entity_id);
CREATE INDEX ix_entity_alias_normalized_name ON entity_alias (normalized_name);
CREATE INDEX ix_retrieval_attempt_run_id ON retrieval_attempt (run_id);
CREATE INDEX ix_candidate_build_id ON candidate (build_id);
CREATE VIEW facility_alias AS SELECT a.* FROM entity_alias a JOIN entities e ON e.id=a.entity_id WHERE e.kind='facility';
CREATE INDEX ix_observations_entity_id ON observations (entity_id);
CREATE VIEW capacity_observation AS SELECT o.*, d.normalized_value AS exact_value FROM observations o JOIN observation_detail d ON d.observation_id=o.id WHERE o.attribute='capacity';
CREATE VIEW status_observation AS SELECT * FROM observations WHERE attribute='status';
CREATE INDEX ix_source_access_source_id ON source_access (source_id);
CREATE INDEX ix_lead_event_date ON lead (event_date);
CREATE INDEX ix_lead_source_id ON lead (source_id);
CREATE INDEX ix_lead_revision_document_id ON lead_revision (document_id);
CREATE INDEX ix_lead_revision_lead_id ON lead_revision (lead_id);
CREATE INDEX ix_lead_headline_document_id ON lead_headline (document_id);
CREATE INDEX ix_lead_headline_lead_id ON lead_headline (lead_id);
CREATE INDEX ix_asset_dependency_from_entity_id ON asset_dependency (from_entity_id);
CREATE INDEX ix_asset_dependency_product ON asset_dependency (product);
CREATE INDEX ix_asset_dependency_to_entity_id ON asset_dependency (to_entity_id);
CREATE INDEX ix_asset_location_entity_id ON asset_location (entity_id);
CREATE INDEX ix_research_event_instrument ON research_event (instrument);
CREATE INDEX ix_research_event_known_at ON research_event (known_at);
CREATE INDEX ix_research_quote_instrument ON research_quote (instrument);
CREATE INDEX ix_investigation_entry_case_id ON investigation_entry (case_id);
CREATE INDEX ix_investigation_entry_kind ON investigation_entry (kind);
CREATE INDEX ix_investigation_task_case_id ON investigation_task (case_id);
CREATE INDEX ix_investigation_task_assignee ON investigation_task (assignee);
CREATE INDEX ix_investigation_task_due_at ON investigation_task (due_at);
CREATE INDEX ix_investigation_task_status ON investigation_task (status);
CREATE INDEX ix_lead_status_date ON lead (status, event_date, last_seen_at, id);
CREATE INDEX ix_lead_topic_date ON lead (topic_name, event_date, last_seen_at, id);
CREATE INDEX ix_lead_date_seen ON lead (event_date, last_seen_at, id);
COMMIT;
