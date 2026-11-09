-- AFED schema for Supabase Postgres. Run once in the SQL editor, before the API first connects.
--
-- Access model:
--   * The FastAPI service connects as the table owner, so it bypasses RLS and enforces roles
--     itself on every router. That is the primary control.
--   * RLS is defence in depth for anything reaching these tables through the Supabase REST API
--     with the anon key. Policies read the caller's role from public.profiles.
--   * A Supabase Auth user has no access until a row exists for them in public.profiles.
--   * Row policies cannot hide a column, so the grants at the end keep ground-truth labels and
--     full bank accounts API-only, and limit writes to the columns each action changes.
--
-- The table definitions below are generated from backend/app/models.py. Keep the two in step.

CREATE TABLE IF NOT EXISTS entity_baselines (
	id SERIAL NOT NULL, 
	entity_type VARCHAR(20) NOT NULL, 
	entity_id VARCHAR(120) NOT NULL, 
	entity_name VARCHAR(255), 
	category VARCHAR(120), 
	baseline_source VARCHAR(10) NOT NULL, 
	median_amount FLOAT, 
	p25_amount FLOAT, 
	p75_amount FLOAT, 
	median_gap_days FLOAT, 
	median_processing_days FLOAT, 
	history_len INTEGER NOT NULL, 
	usual_bank_account VARCHAR(80), 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entity_baselines_entity_id ON entity_baselines (entity_id);

CREATE TABLE IF NOT EXISTS events (
	id SERIAL NOT NULL, 
	event_id VARCHAR(80) NOT NULL, 
	vendor_id VARCHAR(120) NOT NULL, 
	vendor_name VARCHAR(255), 
	amount FLOAT NOT NULL, 
	invoice_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	invoice_number VARCHAR(120), 
	category VARCHAR(120), 
	department VARCHAR(120), 
	approver_id VARCHAR(120), 
	created_by VARCHAR(120), 
	approval_date TIMESTAMP WITHOUT TIME ZONE, 
	processing_days FLOAT, 
	bank_account VARCHAR(80), 
	vendor_created TIMESTAMP WITHOUT TIME ZONE, 
	po_amount FLOAT, 
	is_anomaly INTEGER, 
	anomaly_type VARCHAR(60), 
	baseline_source VARCHAR(10), 
	baseline_amount FLOAT, 
	expected_amount FLOAT, 
	amt_z FLOAT, 
	amt_ratio FLOAT, 
	freq_z FLOAT, 
	proc_z FLOAT, 
	risk FLOAT, 
	level VARCHAR(10), 
	flags JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_events_category ON events (category);
CREATE INDEX IF NOT EXISTS ix_events_department ON events (department);
CREATE UNIQUE INDEX IF NOT EXISTS ix_events_event_id ON events (event_id);
CREATE INDEX IF NOT EXISTS ix_events_invoice_date ON events (invoice_date);
CREATE INDEX IF NOT EXISTS ix_events_level ON events (level);
CREATE INDEX IF NOT EXISTS ix_events_risk ON events (risk);
CREATE INDEX IF NOT EXISTS ix_events_vendor_id ON events (vendor_id);

CREATE TABLE IF NOT EXISTS settings (
	id INTEGER NOT NULL, 
	data JSON NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(100) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	preferences JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_login TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS audit_log (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	entity_type VARCHAR(30) NOT NULL, 
	entity_id VARCHAR(80) NOT NULL, 
	detail JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log (created_at);

CREATE TABLE IF NOT EXISTS cases (
	id SERIAL NOT NULL, 
	vendor_id VARCHAR(120) NOT NULL, 
	vendor_name VARCHAR(255), 
	window_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	assignee_id INTEGER, 
	notes JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assignee_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_cases_status ON cases (status);
CREATE INDEX IF NOT EXISTS ix_cases_vendor_id ON cases (vendor_id);

CREATE TABLE IF NOT EXISTS notifications (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	link VARCHAR(200) NOT NULL, 
	read BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications (user_id, read);

CREATE TABLE IF NOT EXISTS runs (
	id SERIAL NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	stage VARCHAR(80) NOT NULL, 
	progress INTEGER NOT NULL, 
	source VARCHAR(255) NOT NULL, 
	rows INTEGER NOT NULL, 
	new_rows INTEGER NOT NULL, 
	alerts_count INTEGER NOT NULL, 
	model_version VARCHAR(40), 
	metrics JSON, 
	error TEXT, 
	created_by INTEGER, 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS alerts (
	id SERIAL NOT NULL, 
	event_pk INTEGER NOT NULL, 
	vendor_id VARCHAR(120) NOT NULL, 
	risk FLOAT NOT NULL, 
	level VARCHAR(10) NOT NULL, 
	a_score FLOAT NOT NULL, 
	d_score FLOAT NOT NULL, 
	f_score FLOAT NOT NULL, 
	lstm_score FLOAT, 
	flags JSON NOT NULL, 
	facts JSON NOT NULL, 
	explanation TEXT NOT NULL, 
	explanation_provider VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	assignee_id INTEGER, 
	case_id INTEGER, 
	run_id INTEGER, 
	model_version VARCHAR(40), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event_pk), 
	FOREIGN KEY(event_pk) REFERENCES events (id) ON DELETE CASCADE, 
	FOREIGN KEY(assignee_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE SET NULL, 
	FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_alerts_case_id ON alerts (case_id);
CREATE INDEX IF NOT EXISTS ix_alerts_level ON alerts (level);
CREATE INDEX IF NOT EXISTS ix_alerts_risk ON alerts (risk);
CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS ix_alerts_vendor_id ON alerts (vendor_id);

CREATE TABLE IF NOT EXISTS feedback (
	id SERIAL NOT NULL, 
	alert_id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(20) NOT NULL, 
	label INTEGER, 
	reason VARCHAR(120) NOT NULL, 
	comment TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alert_id) REFERENCES alerts (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_feedback_alert_id ON feedback (alert_id);
CREATE INDEX IF NOT EXISTS ix_feedback_created_at ON feedback (created_at);

-- Links a Supabase Auth user to a role and, optionally, to an AFED user.
CREATE TABLE IF NOT EXISTS public.profiles (
	id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
	role TEXT NOT NULL DEFAULT 'Viewer' CHECK (role IN ('Admin', 'Analyst', 'Reviewer', 'Viewer')),
	app_user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- SECURITY DEFINER, because a policy on profiles that read profiles directly would recurse.
CREATE OR REPLACE FUNCTION public.afed_role() RETURNS TEXT
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
	SELECT role FROM public.profiles WHERE id = auth.uid()
$$;

CREATE OR REPLACE FUNCTION public.afed_user_id() RETURNS INTEGER
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
	SELECT app_user_id FROM public.profiles WHERE id = auth.uid()
$$;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- users has RLS and no policy on purpose: it holds password hashes, so only the API may read it.

CREATE POLICY profiles_read ON profiles FOR SELECT TO authenticated
	USING (id = auth.uid() OR public.afed_role() = 'Admin');
CREATE POLICY profiles_admin ON profiles FOR UPDATE TO authenticated
	USING (public.afed_role() = 'Admin') WITH CHECK (public.afed_role() = 'Admin');

-- Dashboard, Entities, Evaluation, Reports, Alerts and Cases: every role can read.
CREATE POLICY events_read ON events FOR SELECT TO authenticated USING (public.afed_role() IS NOT NULL);
CREATE POLICY baselines_read ON entity_baselines FOR SELECT TO authenticated USING (public.afed_role() IS NOT NULL);
CREATE POLICY alerts_read ON alerts FOR SELECT TO authenticated USING (public.afed_role() IS NOT NULL);
CREATE POLICY cases_read ON cases FOR SELECT TO authenticated USING (public.afed_role() IS NOT NULL);
CREATE POLICY feedback_read ON feedback FOR SELECT TO authenticated USING (public.afed_role() IS NOT NULL);

-- Alerts and Cases: Admin and Reviewer act.
CREATE POLICY alerts_act ON alerts FOR UPDATE TO authenticated
	USING (public.afed_role() IN ('Admin', 'Reviewer')) WITH CHECK (public.afed_role() IN ('Admin', 'Reviewer'));
CREATE POLICY cases_act ON cases FOR UPDATE TO authenticated
	USING (public.afed_role() IN ('Admin', 'Reviewer')) WITH CHECK (public.afed_role() IN ('Admin', 'Reviewer'));
CREATE POLICY feedback_act ON feedback FOR INSERT TO authenticated
	WITH CHECK (public.afed_role() IN ('Admin', 'Reviewer') AND user_id = public.afed_user_id());

-- Data Upload and Model Settings: Admin and Analyst.
CREATE POLICY runs_operate ON runs FOR SELECT TO authenticated USING (public.afed_role() IN ('Admin', 'Analyst'));
CREATE POLICY settings_read ON settings FOR SELECT TO authenticated USING (public.afed_role() IN ('Admin', 'Analyst'));
CREATE POLICY settings_write ON settings FOR UPDATE TO authenticated
	USING (public.afed_role() IN ('Admin', 'Analyst')) WITH CHECK (public.afed_role() IN ('Admin', 'Analyst'));

-- A user's own notifications only.
CREATE POLICY notifications_own ON notifications FOR SELECT TO authenticated USING (user_id = public.afed_user_id());
CREATE POLICY notifications_read ON notifications FOR UPDATE TO authenticated
	USING (user_id = public.afed_user_id()) WITH CHECK (user_id = public.afed_user_id());

-- Audit log: Admin reads, nobody writes through the REST API.
CREATE POLICY audit_admin ON audit_log FOR SELECT TO authenticated USING (public.afed_role() = 'Admin');

-- Supabase grants anon and authenticated everything on new tables, so narrow that here.
REVOKE ALL ON users, profiles, events, entity_baselines, runs, alerts, cases, feedback, settings, notifications, audit_log FROM anon;
REVOKE ALL ON users, events, entity_baselines FROM authenticated;
GRANT SELECT (id, event_id, vendor_id, vendor_name, amount, invoice_date, invoice_number, category, department, approver_id, created_by,
	approval_date, processing_days, vendor_created, po_amount, baseline_source, baseline_amount, expected_amount, amt_z, amt_ratio,
	freq_z, proc_z, risk, level, flags) ON events TO authenticated;
GRANT SELECT (id, entity_type, entity_id, entity_name, category, baseline_source, median_amount, p25_amount, p75_amount,
	median_gap_days, median_processing_days, history_len, updated_at) ON entity_baselines TO authenticated;
REVOKE UPDATE ON alerts, cases, notifications FROM authenticated;
GRANT UPDATE (status, assignee_id) ON alerts TO authenticated;
GRANT UPDATE (status, assignee_id, notes) ON cases TO authenticated;
GRANT UPDATE (read) ON notifications TO authenticated;
