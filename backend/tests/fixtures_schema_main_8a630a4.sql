-- Esquema real do banco criado pela main em 8a630a4 (Etapa 2), antes da Etapa 3.
-- Gerado executando `python -m app prepare` com o código daquele commit.
CREATE TABLE activities (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	wbs_id INTEGER, 
	name VARCHAR(255) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	description TEXT, 
	duration FLOAT NOT NULL, 
	quantity FLOAT, 
	unit VARCHAR(30), 
	productivity FLOAT, 
	optimistic FLOAT, 
	most_likely FLOAT, 
	pessimistic FLOAT, 
	percent_complete FLOAT NOT NULL, 
	status VARCHAR(50), 
	es FLOAT, 
	ef FLOAT, 
	ls FLOAT, 
	lf FLOAT, 
	tf FLOAT, 
	ff FLOAT, 
	is_critical INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(wbs_id) REFERENCES wbs_nodes (id) ON DELETE SET NULL
);
CREATE TABLE activity_ifc_elements (
	id INTEGER NOT NULL, 
	activity_id INTEGER NOT NULL, 
	ifc_element_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_activity_ifc_element UNIQUE (activity_id, ifc_element_id), 
	FOREIGN KEY(activity_id) REFERENCES activities (id) ON DELETE CASCADE, 
	FOREIGN KEY(ifc_element_id) REFERENCES ifc_elements (id) ON DELETE CASCADE
);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE ifc_elements (
	id INTEGER NOT NULL, 
	model_id INTEGER NOT NULL, 
	global_id VARCHAR(50) NOT NULL, 
	name VARCHAR(255), 
	ifc_type VARCHAR(100) NOT NULL, 
	description VARCHAR(500), 
	object_type VARCHAR(255), 
	predefined_type VARCHAR(100), 
	properties_json TEXT, 
	quantities_json TEXT, 
	materials_json TEXT, 
	storey_name VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(model_id) REFERENCES ifc_models (id) ON DELETE CASCADE
);
CREATE TABLE ifc_models (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	error_message TEXT, 
	schema_name VARCHAR(50), 
	element_count INTEGER NOT NULL, 
	progress INTEGER NOT NULL, 
	processing_message VARCHAR(255), 
	uploaded_at DATETIME, 
	job_id VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE TABLE jobs (
	id VARCHAR(32) NOT NULL, 
	kind VARCHAR(50) NOT NULL, 
	project_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	progress INTEGER NOT NULL, 
	message VARCHAR(500), 
	error TEXT, 
	params_json TEXT, 
	result_json TEXT, 
	cancel_requested BOOLEAN NOT NULL, 
	cancel_requested_at DATETIME, 
	pid INTEGER, 
	created_at DATETIME NOT NULL, 
	started_at DATETIME, 
	updated_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
);
CREATE TABLE precedences (
	id INTEGER NOT NULL, 
	predecessor_id INTEGER NOT NULL, 
	successor_id INTEGER NOT NULL, 
	relation_type VARCHAR(10) NOT NULL, 
	lag FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(predecessor_id) REFERENCES activities (id) ON DELETE CASCADE, 
	FOREIGN KEY(successor_id) REFERENCES activities (id) ON DELETE CASCADE
);
CREATE TABLE projects (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	client VARCHAR(255), 
	description TEXT, 
	start_date VARCHAR(50), 
	end_date VARCHAR(50), 
	status VARCHAR(50), 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE wbs_nodes (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	description TEXT, 
	parent_id INTEGER, 
	sort_order INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_id) REFERENCES wbs_nodes (id) ON DELETE CASCADE
);
CREATE INDEX ix_activities_id ON activities (id);
CREATE INDEX ix_activities_project_id ON activities (project_id);
CREATE INDEX ix_activities_wbs_id ON activities (wbs_id);
CREATE INDEX ix_activity_ifc_elements_activity_id ON activity_ifc_elements (activity_id);
CREATE INDEX ix_activity_ifc_elements_id ON activity_ifc_elements (id);
CREATE INDEX ix_activity_ifc_elements_ifc_element_id ON activity_ifc_elements (ifc_element_id);
CREATE INDEX ix_ifc_elements_global_id ON ifc_elements (global_id);
CREATE INDEX ix_ifc_elements_id ON ifc_elements (id);
CREATE INDEX ix_ifc_elements_model_id ON ifc_elements (model_id);
CREATE INDEX ix_ifc_models_id ON ifc_models (id);
CREATE INDEX ix_ifc_models_job_id ON ifc_models (job_id);
CREATE INDEX ix_ifc_models_project_id ON ifc_models (project_id);
CREATE INDEX ix_jobs_kind ON jobs (kind);
CREATE INDEX ix_jobs_project_id ON jobs (project_id);
CREATE INDEX ix_jobs_status ON jobs (status);
CREATE INDEX ix_precedences_id ON precedences (id);
CREATE INDEX ix_precedences_predecessor_id ON precedences (predecessor_id);
CREATE INDEX ix_precedences_successor_id ON precedences (successor_id);
CREATE UNIQUE INDEX ix_projects_code ON projects (code);
CREATE INDEX ix_projects_id ON projects (id);
CREATE INDEX ix_projects_name ON projects (name);
CREATE INDEX ix_wbs_nodes_id ON wbs_nodes (id);
CREATE INDEX ix_wbs_nodes_parent_id ON wbs_nodes (parent_id);
CREATE INDEX ix_wbs_nodes_project_id ON wbs_nodes (project_id);
