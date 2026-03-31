-- BankOfferAI database schema (with compliance tables)
-- Drop order respects FK dependencies
DROP TABLE IF EXISTS recommendation_overrides CASCADE;
DROP TABLE IF EXISTS suitability_confirmations CASCADE;
DROP TABLE IF EXISTS ai_act_risk_register CASCADE;
DROP TABLE IF EXISTS model_kill_switch CASCADE;
DROP TABLE IF EXISTS recommendation_feedback CASCADE;
DROP TABLE IF EXISTS audit_recommendations CASCADE;
DROP TABLE IF EXISTS customer_profiles CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS customer_features CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- ===== Core tables =====

CREATE TABLE customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    external_id UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    age INTEGER,
    city VARCHAR(100),
    income NUMERIC(12,2),
    savings NUMERIC(12,2),
    debt NUMERIC(12,2),
    has_debt BOOLEAN DEFAULT FALSE,
    risk_profile VARCHAR(50),
    marital_status VARCHAR(50),
    dependents_count INTEGER DEFAULT 0,
    homeowner_status VARCHAR(50),
    existing_products TEXT,
    financial_health VARCHAR(20) DEFAULT 'stable',
    -- Consent #1: General financial profiling (GDPR Art. 6(1)(a))
    profiling_consent BOOLEAN DEFAULT FALSE,
    profiling_consent_ts TIMESTAMP,
    -- Consent #2: Automated decisions (GDPR Art. 22)
    automated_decision_consent BOOLEAN DEFAULT FALSE,
    automated_decision_consent_ts TIMESTAMP,
    -- Consent #3: Marketing per channel (ePrivacy Directive)
    marketing_push BOOLEAN DEFAULT FALSE,
    marketing_push_ts TIMESTAMP,
    marketing_email BOOLEAN DEFAULT FALSE,
    marketing_email_ts TIMESTAMP,
    marketing_sms BOOLEAN DEFAULT FALSE,
    marketing_sms_ts TIMESTAMP,
    -- Consent #4: Family context — special category data (GDPR Art. 9)
    family_context_consent BOOLEAN DEFAULT FALSE,
    family_context_consent_ts TIMESTAMP,
    -- Legacy field kept for backward compat (maps to family_context_consent)
    sensitive_data_consent BOOLEAN DEFAULT FALSE,
    sensitive_data_consent_ts TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE customer_features (
    customer_id VARCHAR(50) PRIMARY KEY REFERENCES customers(customer_id),
    age INTEGER,
    annual_income NUMERIC(12,2),
    dependents INTEGER DEFAULT 0,
    account_tenure_years NUMERIC(5,2) DEFAULT 0,
    investment_balance NUMERIC(12,2) DEFAULT 0,
    savings_rate NUMERIC(10,4) DEFAULT 0,
    debt_to_income NUMERIC(10,4) DEFAULT 0,
    monthly_savings NUMERIC(12,2) DEFAULT 0,
    avg_expenses NUMERIC(12,2) DEFAULT 0,
    idle_cash NUMERIC(12,2) DEFAULT 0,
    balance_trend VARCHAR(50),
    dominant_spend_category VARCHAR(100),
    investment_gap_flag INTEGER DEFAULT 0,
    risk_profile VARCHAR(50),
    city VARCHAR(100),
    marital_status VARCHAR(50),
    homeowner_status VARCHAR(50),
    existing_products TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    transaction_date TIMESTAMP,
    amount NUMERIC(12,2),
    category VARCHAR(100),
    channel VARCHAR(100),
    recurring_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    event_type VARCHAR(100),
    event_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE products (
    product_name VARCHAR(200) PRIMARY KEY,
    category VARCHAR(100),
    short_description TEXT,
    channel VARCHAR(100),
    priority VARCHAR(50),
    lifecycle_stage VARCHAR(100),
    when_to_recommend TEXT
);

CREATE TABLE customer_profiles (
    customer_id VARCHAR(50) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== Compliance tables =====

-- Requirement 4: Immutable audit trail for every recommendation
CREATE TABLE audit_recommendations (
    id SERIAL PRIMARY KEY,
    recommendation_id UUID NOT NULL UNIQUE,
    external_customer_id UUID NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    input_features JSONB NOT NULL,
    profile_result JSONB NOT NULL,
    suitability_checks JSONB NOT NULL,
    scored_products JSONB NOT NULL,
    final_offers JSONB NOT NULL,
    excluded_products JSONB DEFAULT '[]',
    model_version VARCHAR(50) NOT NULL,
    consent_snapshot JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Requirement 3: Human-in-the-loop feedback
CREATE TABLE recommendation_feedback (
    id SERIAL PRIMARY KEY,
    recommendation_id UUID NOT NULL,
    offer_id VARCHAR(100) NOT NULL,
    product_id VARCHAR(100),
    customer_id VARCHAR(50),
    actor_type VARCHAR(20) NOT NULL CHECK (actor_type IN ('customer', 'employee')),
    actor_id VARCHAR(100),
    action VARCHAR(20) NOT NULL CHECK (action IN ('accepted', 'rejected', 'flagged', 'overridden')),
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Consent #5: MiFID II suitability confirmation per product (Art. 25)
CREATE TABLE suitability_confirmations (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    product_id VARCHAR(100) NOT NULL,
    recommendation_id UUID,
    risk_profile_at_confirmation VARCHAR(50) NOT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI Act Art. 14: Model kill-switch for emergency suspension
CREATE TABLE model_kill_switch (
    id SERIAL PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    activated_by VARCHAR(100),
    reason TEXT,
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI Act Art. 9: Risk register — living document per model version
CREATE TABLE ai_act_risk_register (
    id SERIAL PRIMARY KEY,
    risk_id VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    mitigation TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'mitigated', 'accepted', 'closed')),
    owner VARCHAR(100),
    model_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- AI Act Art. 14: Employee overrides of recommendations
CREATE TABLE recommendation_overrides (
    id SERIAL PRIMARY KEY,
    recommendation_id UUID NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(100) NOT NULL,
    product_id VARCHAR(100),
    override_type VARCHAR(30) NOT NULL CHECK (override_type IN ('reject', 'suppress', 'escalate')),
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== Indexes =====
CREATE INDEX idx_customer_features_cid ON customer_features(customer_id);
CREATE INDEX idx_transactions_cid ON transactions(customer_id);
CREATE INDEX idx_events_cid ON events(customer_id);
CREATE INDEX idx_customers_external_id ON customers(external_id);
CREATE INDEX idx_audit_customer ON audit_recommendations(customer_id);
CREATE INDEX idx_audit_external_cid ON audit_recommendations(external_customer_id);
CREATE INDEX idx_audit_created ON audit_recommendations(created_at);
CREATE INDEX idx_feedback_rec ON recommendation_feedback(recommendation_id);
CREATE INDEX idx_feedback_customer ON recommendation_feedback(customer_id);
CREATE INDEX idx_suitability_customer ON suitability_confirmations(customer_id);
CREATE INDEX idx_suitability_product ON suitability_confirmations(product_id);
CREATE INDEX idx_overrides_rec ON recommendation_overrides(recommendation_id);
CREATE INDEX idx_overrides_customer ON recommendation_overrides(customer_id);
CREATE INDEX idx_risk_register_status ON ai_act_risk_register(status);

-- Insert default kill-switch state (inactive)
INSERT INTO model_kill_switch (active, reason) VALUES (FALSE, 'System initialized — model active');

-- Seed initial risk register entries (AI Act Art. 9)
INSERT INTO ai_act_risk_register (risk_id, category, description, severity, mitigation, status, owner, model_version) VALUES
('RISK-001', 'Bias', 'Model may recommend different products for similar customers based on city/geography', 'high', 'City excluded from all scoring logic. Periodic bias audit across segments.', 'mitigated', 'ML Engineer', 'rules-1.0.0'),
('RISK-002', 'Suitability', 'High-risk products recommended to low-risk customers', 'critical', 'Hard MiFID II suitability filter blocks mismatched risk levels before scoring.', 'mitigated', 'Compliance', 'rules-1.0.0'),
('RISK-003', 'Vulnerable customers', 'Credit products offered to financially fragile customers', 'critical', 'Hard filter: financial_health=fragile excludes all credit products.', 'mitigated', 'Compliance', 'rules-1.0.0'),
('RISK-004', 'Data quality', 'Missing or extreme feature values produce unreliable scores', 'medium', 'Safe defaults for all features. Clamped ranges (savings_rate 0-1, DTI 0-10).', 'mitigated', 'Data Engineer', 'rules-1.0.0'),
('RISK-005', 'Consent violation', 'Processing customer data without valid consent', 'critical', 'Pipeline checks profiling_consent=true before any processing. No consent = zero offers.', 'mitigated', 'Backend Lead', 'rules-1.0.0'),
('RISK-006', 'Family data leakage', 'Marital status/dependents used without Art. 9 consent', 'high', 'Family fields gated behind family_context_consent. Without consent, fields zeroed.', 'mitigated', 'Backend Lead', 'rules-1.0.0'),
('RISK-007', 'Model drift', 'Recommendation distribution shifts significantly from baseline', 'medium', 'Monitoring via recommendation distribution tracking. Alert threshold at 15% deviation.', 'open', 'ML Engineer', 'rules-1.0.0'),
('RISK-008', 'Automated decision impact', 'Offers generated without human review for high-impact products', 'high', 'Automated_decision_consent required for fully automatic offers. Without it, human_review_required flag set.', 'mitigated', 'Compliance', 'rules-1.0.0'),
('RISK-009', 'Manipulative UI', 'Urgency tactics or pressure in offer presentation', 'high', 'No countdown timers, no false scarcity. Neutral offer language verified.', 'mitigated', 'UX Lead', 'rules-1.0.0'),
('RISK-010', 'Protected characteristics inference', 'Spend categories could infer religion/ethnicity', 'medium', 'Only broad spend categories used (travel, shopping, rent). No sub-category inference.', 'mitigated', 'ML Engineer', 'rules-1.0.0');
