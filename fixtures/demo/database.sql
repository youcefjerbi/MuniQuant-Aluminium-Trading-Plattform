BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('fcf5b3d9e812');
CREATE TABLE audit (
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	actor VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	record_id VARCHAR NOT NULL, 
	detail JSON NOT NULL, 
	PRIMARY KEY (id)
);
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
INSERT INTO "company" VALUES('0e9a2eee-00dc-463c-a4bd-7056a3a60b62');
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
	CONSTRAINT ck_relationship_role CHECK (role IN ('OWNS','OPERATES')), 
	CONSTRAINT ck_relationship_interval CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	CONSTRAINT ck_relationship_share CHECK (percentage IS NULL OR (CAST(percentage AS NUMERIC) >= 0 AND CAST(percentage AS NUMERIC) <= 100)), 
	FOREIGN KEY(company_id) REFERENCES company (entity_id), 
	FOREIGN KEY(relationship_id) REFERENCES relationships (id), 
	FOREIGN KEY(document_id) REFERENCES document_version (document_id), 
	FOREIGN KEY(facility_id) REFERENCES facility (entity_id)
);
INSERT INTO "company_facility_relationship" VALUES('7fb5191d-c4c6-4a41-9d7e-1a217aeed0c7','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','ef398f21-ea1a-4a9a-aa57-87d826a2e219','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: Nordhaven Smelter','100','2025-01-01',NULL);
INSERT INTO "company_facility_relationship" VALUES('6a5bac21-f07c-4fa0-8d63-c197a6f5847e','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','a6b12e3d-ffd4-42f5-ae43-53dc377c9686','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: Riverton Aluminium','100','2025-01-01',NULL);
INSERT INTO "company_facility_relationship" VALUES('9bcb3e8d-d2b0-44ed-8b16-c160c5882387','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','ee392aab-e574-450a-b225-8d66a027e804','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: Coastal Alumina Works','100','2025-01-01',NULL);
INSERT INTO "company_facility_relationship" VALUES('4090763f-476c-4be7-b9c7-f3f152a5aa1d','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','7ce373d2-6886-4cfe-a54f-c35d6c864cab','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: Highland Bauxite Mine','100','2025-01-01',NULL);
INSERT INTO "company_facility_relationship" VALUES('633b0fb1-ec8e-4333-a216-3005484f0c25','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: East Bay Smelter','100','2025-01-01',NULL);
INSERT INTO "company_facility_relationship" VALUES('ff3f7580-b8c6-4faf-b851-1329e8c8be15','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','fe0bde46-603c-430a-b5d1-57b401479e74','b0193414-6add-4707-9725-df7669bcaa20','OWNS','Fictional register: Gulf Aluminium Works','100','2025-01-01',NULL);
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
INSERT INTO "document_version" VALUES('b0193414-6add-4707-9725-df7669bcaa20','77b15557eff1ff60f15f2e34cd3a1b66a7494a6cc4a61b0464aeb66aa3e26624',1);
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
INSERT INTO "documents" VALUES('b0193414-6add-4707-9725-df7669bcaa20','ae9bc2d3-94cb-43ac-b93c-f6d468853b91','Fictional industrial capacity register 2025','https://example.org/muniquant-demo/industrial-2025','2025-01-01','2026-10-10T22:48:05.922027+00:00','text/plain','77b15557eff1ff60f15f2e34cd3a1b66a7494a6cc4a61b0464aeb66aa3e26624',1);
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
INSERT INTO "entities" VALUES('0e9a2eee-00dc-463c-a4bd-7056a3a60b62','Example Metals Group','company',NULL,'DE','Europe','aluminium','[]');
INSERT INTO "entities" VALUES('ef398f21-ea1a-4a9a-aa57-87d826a2e219','Nordhaven Smelter','facility','smelter','NO','Europe','aluminium','["Nordhaven Works"]');
INSERT INTO "entities" VALUES('a6b12e3d-ffd4-42f5-ae43-53dc377c9686','Riverton Aluminium','facility','smelter','CA','North America','aluminium','[]');
INSERT INTO "entities" VALUES('ee392aab-e574-450a-b225-8d66a027e804','Coastal Alumina Works','facility','refinery','AU','Oceania','alumina','[]');
INSERT INTO "entities" VALUES('7ce373d2-6886-4cfe-a54f-c35d6c864cab','Highland Bauxite Mine','facility','bauxite_mine','GN','Africa','bauxite','[]');
INSERT INTO "entities" VALUES('7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','East Bay Smelter','facility','smelter','CN','Asia','aluminium','["East Bay Works"]');
INSERT INTO "entities" VALUES('fe0bde46-603c-430a-b5d1-57b401479e74','Gulf Aluminium Works','facility','smelter','AE','Middle East','aluminium','[]');
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
INSERT INTO "entity_alias" VALUES('c9266da1-d713-48fe-b7b7-bb3c8d5c948c','ef398f21-ea1a-4a9a-aa57-87d826a2e219','Nordhaven Works','nordhaven works','fixture-curator','Initial curated alias','2026-10-10T22:48:05.925067+00:00');
INSERT INTO "entity_alias" VALUES('a5cf4861-3bc5-4052-a8d4-057f09c14298','7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','East Bay Works','east bay works','fixture-curator','Initial curated alias','2026-10-10T22:48:05.930904+00:00');
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
INSERT INTO "entity_evidence" VALUES('ef398f21-ea1a-4a9a-aa57-87d826a2e219','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: Nordhaven Smelter','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.927179+00:00');
INSERT INTO "entity_evidence" VALUES('a6b12e3d-ffd4-42f5-ae43-53dc377c9686','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: Riverton Aluminium','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.928318+00:00');
INSERT INTO "entity_evidence" VALUES('ee392aab-e574-450a-b225-8d66a027e804','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: Coastal Alumina Works','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.929309+00:00');
INSERT INTO "entity_evidence" VALUES('7ce373d2-6886-4cfe-a54f-c35d6c864cab','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: Highland Bauxite Mine','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.930264+00:00');
INSERT INTO "entity_evidence" VALUES('7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: East Bay Smelter','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.931373+00:00');
INSERT INTO "entity_evidence" VALUES('fe0bde46-603c-430a-b5d1-57b401479e74','b0193414-6add-4707-9725-df7669bcaa20','Synthetic register: Gulf Aluminium Works','fixture-curator','Explicit fictional development fixture, not verified industrial data','2026-10-10T22:48:05.932315+00:00');
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
INSERT INTO "facility" VALUES('ef398f21-ea1a-4a9a-aa57-87d826a2e219','smelter','NO','a1aca172-797f-4c60-92a7-146271d987b9','aluminium');
INSERT INTO "facility" VALUES('a6b12e3d-ffd4-42f5-ae43-53dc377c9686','smelter','CA','14df2915-7adb-4518-bb44-0b1775fa0e8c','aluminium');
INSERT INTO "facility" VALUES('ee392aab-e574-450a-b225-8d66a027e804','refinery','AU','49e8e25b-c65e-4782-b8ab-88972b88b55b','alumina');
INSERT INTO "facility" VALUES('7ce373d2-6886-4cfe-a54f-c35d6c864cab','bauxite_mine','GN','cd2c70f8-61be-4c07-95e5-abf94a566c3d','bauxite');
INSERT INTO "facility" VALUES('7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','smelter','CN','d88987e1-6a4b-4b7a-ae46-645f77d3cdb3','aluminium');
INSERT INTO "facility" VALUES('fe0bde46-603c-430a-b5d1-57b401479e74','smelter','AE','d4a75b9a-8ca2-44a1-8eac-7c18edfb902f','aluminium');
CREATE TABLE facility_type (
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (code)
);
INSERT INTO "facility_type" VALUES('smelter','Primary aluminium smelter');
INSERT INTO "facility_type" VALUES('refinery','Alumina refinery');
INSERT INTO "facility_type" VALUES('bauxite_mine','Bauxite mine');
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
INSERT INTO "observation_detail" VALUES('77d4cc42-5d26-4753-b769-3679a5935be9','420000','t/year','2025-01-01',NULL);
INSERT INTO "observation_detail" VALUES('bcab9fd1-830d-4dd0-9387-d7890cfab9f3','310000','t/year','2025-01-01',NULL);
INSERT INTO "observation_detail" VALUES('2a419c04-617b-4c38-9816-9fe530c60978','1800000','t/year','2025-01-01',NULL);
INSERT INTO "observation_detail" VALUES('91412f74-84fc-4f4c-91bd-ad4527c9bd07','2400000','t/year','2025-01-01',NULL);
INSERT INTO "observation_detail" VALUES('d4c9e7f8-16d4-4c7f-9c5a-7da62e24080b','560000','t/year','2025-01-01',NULL);
INSERT INTO "observation_detail" VALUES('3e0e91d7-893e-447f-8c88-4244256d330e','720000','t/year','2025-01-01',NULL);
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
	CONSTRAINT ck_observation_nonnegative CHECK (normalized_value IS NULL OR normalized_value >= 0), 
	CONSTRAINT ck_observation_interval CHECK (valid_to IS NULL OR valid_to >= valid_from), 
	CONSTRAINT ck_observation_dimension CHECK ((attribute='capacity' AND reported_unit IN ('t/year','kt/year','Mt/year')) OR (attribute='power' AND reported_unit='MW') OR (attribute='ownership_percentage' AND reported_unit='percentage') OR (attribute='status' AND reported_unit='status')), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id)
);
INSERT INTO "observations" VALUES('77d4cc42-5d26-4753-b769-3679a5935be9','ef398f21-ea1a-4a9a-aa57-87d826a2e219','b0193414-6add-4707-9725-df7669bcaa20','capacity','420','kt/year',420000.0,'t/year','2025-01-01',NULL,'Synthetic register: Nordhaven Smelter','PASS','[]','2026-10-10T22:48:05.925881+00:00','manual-v1');
INSERT INTO "observations" VALUES('bcab9fd1-830d-4dd0-9387-d7890cfab9f3','a6b12e3d-ffd4-42f5-ae43-53dc377c9686','b0193414-6add-4707-9725-df7669bcaa20','capacity','310','kt/year',310000.0,'t/year','2025-01-01',NULL,'Synthetic register: Riverton Aluminium','PASS','[]','2026-10-10T22:48:05.927998+00:00','manual-v1');
INSERT INTO "observations" VALUES('2a419c04-617b-4c38-9816-9fe530c60978','ee392aab-e574-450a-b225-8d66a027e804','b0193414-6add-4707-9725-df7669bcaa20','capacity','1800','kt/year',1800000.0,'t/year','2025-01-01',NULL,'Synthetic register: Coastal Alumina Works','PASS','[]','2026-10-10T22:48:05.929005+00:00','manual-v1');
INSERT INTO "observations" VALUES('91412f74-84fc-4f4c-91bd-ad4527c9bd07','7ce373d2-6886-4cfe-a54f-c35d6c864cab','b0193414-6add-4707-9725-df7669bcaa20','capacity','2400','kt/year',2400000.0,'t/year','2025-01-01',NULL,'Synthetic register: Highland Bauxite Mine','PASS','[]','2026-10-10T22:48:05.929970+00:00','manual-v1');
INSERT INTO "observations" VALUES('d4c9e7f8-16d4-4c7f-9c5a-7da62e24080b','7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','b0193414-6add-4707-9725-df7669bcaa20','capacity','560','kt/year',560000.0,'t/year','2025-01-01',NULL,'Synthetic register: East Bay Smelter','PASS','[]','2026-10-10T22:48:05.931073+00:00','manual-v1');
INSERT INTO "observations" VALUES('3e0e91d7-893e-447f-8c88-4244256d330e','fe0bde46-603c-430a-b5d1-57b401479e74','b0193414-6add-4707-9725-df7669bcaa20','capacity','720','kt/year',720000.0,'t/year','2025-01-01',NULL,'Synthetic register: Gulf Aluminium Works','PASS','[]','2026-10-10T22:48:05.932041+00:00','manual-v1');
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
CREATE TABLE region (
	id VARCHAR NOT NULL, 
	country_code VARCHAR(2) NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(country_code) REFERENCES country (code), 
	UNIQUE (country_code, name)
);
INSERT INTO "region" VALUES('a1aca172-797f-4c60-92a7-146271d987b9','NO','Europe');
INSERT INTO "region" VALUES('14df2915-7adb-4518-bb44-0b1775fa0e8c','CA','North America');
INSERT INTO "region" VALUES('49e8e25b-c65e-4782-b8ab-88972b88b55b','AU','Oceania');
INSERT INTO "region" VALUES('cd2c70f8-61be-4c07-95e5-abf94a566c3d','GN','Africa');
INSERT INTO "region" VALUES('d88987e1-6a4b-4b7a-ae46-645f77d3cdb3','CN','Asia');
INSERT INTO "region" VALUES('d4a75b9a-8ca2-44a1-8eac-7c18edfb902f','AE','Middle East');
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
INSERT INTO "relationships" VALUES('7fb5191d-c4c6-4a41-9d7e-1a217aeed0c7','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','ef398f21-ea1a-4a9a-aa57-87d826a2e219','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
INSERT INTO "relationships" VALUES('6a5bac21-f07c-4fa0-8d63-c197a6f5847e','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','a6b12e3d-ffd4-42f5-ae43-53dc377c9686','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
INSERT INTO "relationships" VALUES('9bcb3e8d-d2b0-44ed-8b16-c160c5882387','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','ee392aab-e574-450a-b225-8d66a027e804','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
INSERT INTO "relationships" VALUES('4090763f-476c-4be7-b9c7-f3f152a5aa1d','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','7ce373d2-6886-4cfe-a54f-c35d6c864cab','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
INSERT INTO "relationships" VALUES('633b0fb1-ec8e-4333-a216-3005484f0c25','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','7d1c3c02-a8e1-4b42-a4ad-7bd90104328c','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
INSERT INTO "relationships" VALUES('ff3f7580-b8c6-4faf-b851-1329e8c8be15','0e9a2eee-00dc-463c-a4bd-7056a3a60b62','fe0bde46-603c-430a-b5d1-57b401479e74','OWNS',100.0,'2025-01-01',NULL,'b0193414-6add-4707-9725-df7669bcaa20');
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
INSERT INTO "reviews" VALUES('7ba3417a-f1d6-4bc9-b386-38ea9ea162f0','Bay aluminium','["7d1c3c02-a8e1-4b42-a4ad-7bd90104328c", "fe0bde46-603c-430a-b5d1-57b401479e74"]','pending',NULL,NULL,NULL,NULL);
CREATE TABLE runs (
	id VARCHAR NOT NULL, 
	started_at VARCHAR NOT NULL, 
	pipeline_version VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	manifest JSON NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "runs" VALUES('a4bf5b17-13c5-4c0e-b6e1-b823d684a5a9','2026-10-10T22:48:05.922924+00:00','1.0.0','success','{"content_hash": "77b15557eff1ff60f15f2e34cd3a1b66a7494a6cc4a61b0464aeb66aa3e26624", "document_id": "b0193414-6add-4707-9725-df7669bcaa20", "adapter": "text-upload-v1"}');
CREATE TABLE source_access (
	id VARCHAR NOT NULL, 
	source_id VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	allowed_hosts JSON NOT NULL, 
	basis TEXT NOT NULL, 
	retention TEXT NOT NULL, 
	reviewer VARCHAR NOT NULL, 
	decided_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_source_access_status CHECK (status IN ('permitted','review_required','restricted')), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
);
CREATE TABLE source_document_relation (
	source_id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	PRIMARY KEY (source_id, document_id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(source_id) REFERENCES sources (id)
);
INSERT INTO "source_document_relation" VALUES('ae9bc2d3-94cb-43ac-b93c-f6d468853b91','b0193414-6add-4707-9725-df7669bcaa20');
CREATE TABLE source_snapshot (
	content_hash VARCHAR(64) NOT NULL, 
	storage_reference VARCHAR NOT NULL, 
	byte_size INTEGER, 
	PRIMARY KEY (content_hash), 
	CONSTRAINT ck_snapshot_size CHECK (byte_size >= 0)
);
INSERT INTO "source_snapshot" VALUES('77b15557eff1ff60f15f2e34cd3a1b66a7494a6cc4a61b0464aeb66aa3e26624','77b15557eff1ff60f15f2e34cd3a1b66a7494a6cc4a61b0464aeb66aa3e26624',299);
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
INSERT INTO "sources" VALUES('ae9bc2d3-94cb-43ac-b93c-f6d468853b91','MuniQuant demonstration dataset','MuniQuant fixtures','synthetic','https://example.org/muniquant-demo','synthetic','Fictional industrial facilities for software testing.');
CREATE INDEX ix_documents_content_hash ON documents (content_hash);
CREATE INDEX ix_documents_source_id ON documents (source_id);
CREATE INDEX ix_market_observations_effective_at ON market_observations (effective_at);
CREATE INDEX ix_market_observations_instrument ON market_observations (instrument);
CREATE INDEX ix_entity_alias_entity_id ON entity_alias (entity_id);
CREATE INDEX ix_entity_alias_normalized_name ON entity_alias (normalized_name);
CREATE INDEX ix_retrieval_attempt_run_id ON retrieval_attempt (run_id);
CREATE INDEX ix_source_access_source_id ON source_access (source_id);
CREATE INDEX ix_candidate_build_id ON candidate (build_id);
CREATE VIEW facility_alias AS SELECT a.* FROM entity_alias a JOIN entities e ON e.id=a.entity_id WHERE e.kind='facility';
CREATE INDEX ix_observations_entity_id ON observations (entity_id);
CREATE VIEW capacity_observation AS SELECT o.*, d.normalized_value AS exact_value FROM observations o JOIN observation_detail d ON d.observation_id=o.id WHERE o.attribute='capacity';
CREATE VIEW status_observation AS SELECT * FROM observations WHERE attribute='status';
COMMIT;
