-- BankOfferAI database schema (with compliance tables)
-- Drop order respects FK dependencies
DROP TABLE IF EXISTS consent_history CASCADE;
DROP TABLE IF EXISTS ai_api_call_log CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS ai_product_suggestions CASCADE;
DROP TABLE IF EXISTS market_intelligence CASCADE;
DROP TABLE IF EXISTS connectors CASCADE;
DROP TABLE IF EXISTS application_forms CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS staff_auth CASCADE;
DROP TABLE IF EXISTS customer_auth CASCADE;
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

-- ===== Connectors (third-party service integrations) =====

CREATE TABLE connectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('ai','cloud','advertising','analytics','crm','messaging','payments','security')),
    provider VARCHAR(200) NOT NULL,
    description TEXT,
    icon VARCHAR(50) DEFAULT 'plug',
    config_schema JSONB NOT NULL DEFAULT '[]',
    config_values JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available','pending','approved','active','disabled','rejected')),
    suggested_by VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ===== Market Intelligence (AI-driven product suggestions) =====

CREATE TABLE market_intelligence (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL CHECK (category IN ('exchange_markets','geopolitics','regulations','economic','trends')),
    title VARCHAR(300) NOT NULL,
    summary TEXT NOT NULL,
    impact VARCHAR(20) NOT NULL CHECK (impact IN ('positive','negative','neutral','mixed')),
    severity VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
    data_points JSONB NOT NULL DEFAULT '{}',
    source VARCHAR(200),
    region VARCHAR(100) DEFAULT 'Global',
    valid_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ai_product_suggestions (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    product_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    target_segments JSONB NOT NULL DEFAULT '[]',
    market_drivers JSONB NOT NULL DEFAULT '[]',
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.5,
    projected_demand VARCHAR(20) DEFAULT 'medium' CHECK (projected_demand IN ('low','medium','high','very_high')),
    risk_level VARCHAR(20) DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
    ai_model_used VARCHAR(100),
    intelligence_ids JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','implemented','expired')),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== Workflow tables (Employee ↔ Customer) =====

-- Notifications sent to employees when customers act on offers
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    offer_id VARCHAR(100) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('accepted', 'rejected', 'submitted')),
    recommendation_id UUID,
    read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Application forms sent by employees to customers
CREATE TABLE application_forms (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    employee_id VARCHAR(100) NOT NULL,
    notification_id INTEGER REFERENCES notifications(id),
    product_name VARCHAR(200) NOT NULL,
    offer_id VARCHAR(100),
    form_type VARCHAR(50) NOT NULL DEFAULT 'product_application',
    fields JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'approved', 'rejected')),
    submitted_data JSONB,
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== Staff authentication =====
CREATE TABLE staff_auth (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,           -- PBKDF2-SHA256 with random salt
    display_name VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'employee')),
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== Customer authentication (GDPR-compliant) =====
CREATE TABLE customer_auth (
    id SERIAL PRIMARY KEY,
    email_hash VARCHAR(64) NOT NULL UNIQUE,       -- SHA-256 hash (irreversible, GDPR Art. 5(1)(c))
    password_hash VARCHAR(200) NOT NULL,           -- PBKDF2-SHA256 with random salt
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    display_name VARCHAR(200),
    anonymize_after TIMESTAMP NOT NULL,            -- GDPR Art. 5(1)(e) storage limitation
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===== API tokens (programmatic access) =====
CREATE TABLE IF NOT EXISTS api_tokens (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    token_prefix VARCHAR(16) NOT NULL,
    scopes VARCHAR(200) NOT NULL DEFAULT 'read',
    created_by VARCHAR(200) NOT NULL,
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
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
CREATE INDEX idx_customer_auth_email ON customer_auth(email_hash);
CREATE INDEX idx_customer_auth_customer ON customer_auth(customer_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_active ON api_tokens(revoked, expires_at);
CREATE INDEX idx_market_intel_category ON market_intelligence(category);
CREATE INDEX idx_market_intel_impact ON market_intelligence(impact);
CREATE INDEX idx_ai_suggestions_status ON ai_product_suggestions(status);
CREATE INDEX idx_ai_suggestions_type ON ai_product_suggestions(product_type);
CREATE INDEX idx_connectors_category ON connectors(category);
CREATE INDEX idx_connectors_status ON connectors(status);
CREATE INDEX idx_notifications_read ON notifications(read, created_at DESC);
CREATE INDEX idx_notifications_customer ON notifications(customer_id);
CREATE INDEX idx_forms_customer ON application_forms(customer_id);
CREATE INDEX idx_forms_status ON application_forms(status);
CREATE INDEX idx_audit_log_actor ON audit_log(actor, created_at DESC);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at DESC);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_request ON audit_log(request_id);
CREATE INDEX idx_ai_api_log_provider ON ai_api_call_log(provider, created_at DESC);
CREATE INDEX idx_ai_api_log_outcome ON ai_api_call_log(outcome, created_at DESC);
CREATE INDEX idx_ai_api_log_created ON ai_api_call_log(created_at DESC);
CREATE INDEX idx_consent_history_customer ON consent_history(customer_id, created_at DESC);
CREATE INDEX idx_consent_history_type ON consent_history(consent_type, created_at DESC);

-- Insert default kill-switch state (inactive)
INSERT INTO model_kill_switch (active, reason) VALUES (FALSE, 'System initialized — model active');

-- Seed connector templates (available integrations)
INSERT INTO connectors (name, category, provider, description, icon, config_schema, status) VALUES
('OpenAI GPT', 'ai', 'OpenAI', 'Generate offer explanations, customer insights, and natural language summaries using GPT models.', 'brain',
 '[{"name":"api_key","label":"API Key","type":"password","required":true,"placeholder":"sk-..."},{"name":"model","label":"Model","type":"select","required":true,"options":["gpt-4o","gpt-4o-mini","gpt-4-turbo"]},{"name":"temperature","label":"Temperature","type":"number","required":false,"placeholder":"0.7"}]', 'available'),
('Claude API', 'ai', 'Anthropic', 'Power offer explanations and compliance reports with Claude. Enhances GDPR Art. 22 transparency.', 'brain',
 '[{"name":"api_key","label":"API Key","type":"password","required":true,"placeholder":"sk-ant-..."},{"name":"model","label":"Model","type":"select","required":true,"options":["claude-sonnet-4-6","claude-haiku-4-5-20251001","claude-opus-4-6"]},{"name":"max_tokens","label":"Max Tokens","type":"number","required":false,"placeholder":"1024"}]', 'available'),
('Google Gemini', 'ai', 'Google', 'Multimodal AI for document analysis, customer onboarding verification, and KYC automation.', 'brain',
 '[{"name":"api_key","label":"API Key","type":"password","required":true},{"name":"model","label":"Model","type":"select","required":true,"options":["gemini-2.5-pro","gemini-2.5-flash"]}]', 'available'),
('Hugging Face', 'ai', 'Hugging Face', 'Deploy custom NLP models for sentiment analysis, product matching, and customer segmentation.', 'brain',
 '[{"name":"api_token","label":"API Token","type":"password","required":true},{"name":"model_id","label":"Model ID","type":"text","required":true,"placeholder":"sentence-transformers/all-MiniLM-L6-v2"}]', 'available'),
('Perplexity AI', 'ai', 'Perplexity', 'Real-time web-grounded AI for market research, competitive analysis, and regulatory monitoring. Responses include live citations.', 'brain',
 '[{"name":"api_key","label":"API Key","type":"password","required":true,"placeholder":"pplx-..."},{"name":"model","label":"Model","type":"select","required":true,"options":["sonar-pro","sonar","sonar-deep-research","sonar-reasoning-pro"]}]', 'available'),
('Local LLM (Ollama)', 'ai', 'Local LLM', 'Connect to a self-hosted Ollama instance. Run Llama, Mistral, Gemma, or any GGUF model on your own hardware — no data leaves your network.', 'brain',
 '[{"name":"base_url","label":"Base URL","type":"url","required":true,"placeholder":"http://localhost:11434"},{"name":"model","label":"Model","type":"text","required":true,"placeholder":"llama3.1:70b"},{"name":"api_key","label":"API Key (optional)","type":"password","required":false,"placeholder":"Leave empty if not required"},{"name":"temperature","label":"Temperature","type":"number","required":false,"placeholder":"0.7"}]', 'available'),
('Local LLM (vLLM)', 'ai', 'Local LLM', 'Connect to a vLLM inference server. High-throughput serving for large models with PagedAttention. OpenAI-compatible endpoint.', 'brain',
 '[{"name":"base_url","label":"Base URL","type":"url","required":true,"placeholder":"http://localhost:8000"},{"name":"model","label":"Model","type":"text","required":true,"placeholder":"meta-llama/Llama-3.1-70B-Instruct"},{"name":"api_key","label":"API Key (optional)","type":"password","required":false},{"name":"temperature","label":"Temperature","type":"number","required":false,"placeholder":"0.7"}]', 'available'),
('Local LLM (LM Studio)', 'ai', 'Local LLM', 'Connect to LM Studio local server. Desktop-friendly way to run GGUF models with an OpenAI-compatible API.', 'brain',
 '[{"name":"base_url","label":"Base URL","type":"url","required":true,"placeholder":"http://localhost:1234"},{"name":"model","label":"Model","type":"text","required":true,"placeholder":"local-model"},{"name":"temperature","label":"Temperature","type":"number","required":false,"placeholder":"0.7"}]', 'available'),
('AWS', 'cloud', 'Amazon Web Services', 'S3 storage, SageMaker ML endpoints, Lambda functions, and SES email delivery.', 'cloud',
 '[{"name":"access_key_id","label":"Access Key ID","type":"password","required":true},{"name":"secret_access_key","label":"Secret Access Key","type":"password","required":true},{"name":"region","label":"Region","type":"select","required":true,"options":["eu-central-1","eu-west-1","us-east-1","ap-southeast-1"]}]', 'available'),
('Microsoft Azure', 'cloud', 'Microsoft', 'Azure ML, Cognitive Services, Blob Storage, and Azure AD integration.', 'cloud',
 '[{"name":"tenant_id","label":"Tenant ID","type":"text","required":true},{"name":"client_id","label":"Client ID","type":"text","required":true},{"name":"client_secret","label":"Client Secret","type":"password","required":true},{"name":"subscription_id","label":"Subscription ID","type":"text","required":true}]', 'available'),
('Google Cloud', 'cloud', 'Google', 'BigQuery analytics, Vertex AI, Cloud Functions, and Firebase integration.', 'cloud',
 '[{"name":"project_id","label":"Project ID","type":"text","required":true},{"name":"service_account_json","label":"Service Account JSON","type":"textarea","required":true,"placeholder":"Paste service account JSON"}]', 'available'),
('Google Ads', 'advertising', 'Google', 'Sync high-value customer segments for targeted product advertising campaigns.', 'megaphone',
 '[{"name":"developer_token","label":"Developer Token","type":"password","required":true},{"name":"client_id","label":"OAuth Client ID","type":"text","required":true},{"name":"client_secret","label":"OAuth Client Secret","type":"password","required":true},{"name":"customer_id","label":"Customer ID","type":"text","required":true,"placeholder":"123-456-7890"}]', 'available'),
('Meta Ads', 'advertising', 'Meta', 'Create lookalike audiences and retarget customers who viewed but did not accept offers.', 'megaphone',
 '[{"name":"access_token","label":"Access Token","type":"password","required":true},{"name":"ad_account_id","label":"Ad Account ID","type":"text","required":true,"placeholder":"act_123456789"},{"name":"pixel_id","label":"Pixel ID","type":"text","required":false}]', 'available'),
('LinkedIn Ads', 'advertising', 'LinkedIn', 'Target B2B banking product campaigns to professionals based on industry and seniority.', 'megaphone',
 '[{"name":"access_token","label":"Access Token","type":"password","required":true},{"name":"account_id","label":"Account ID","type":"text","required":true}]', 'available'),
('Google Analytics 4', 'analytics', 'Google', 'Track offer impressions, acceptance rates, and conversion funnels across portals.', 'chart',
 '[{"name":"measurement_id","label":"Measurement ID","type":"text","required":true,"placeholder":"G-XXXXXXXXXX"},{"name":"api_secret","label":"API Secret","type":"password","required":true}]', 'available'),
('Mixpanel', 'analytics', 'Mixpanel', 'Product analytics for customer journey tracking, A/B testing, and offer funnel optimization.', 'chart',
 '[{"name":"project_token","label":"Project Token","type":"text","required":true},{"name":"api_secret","label":"API Secret","type":"password","required":true}]', 'available'),
('Salesforce CRM', 'crm', 'Salesforce', 'Sync customer profiles and offer history. Enables relationship managers to see AI recommendations.', 'users',
 '[{"name":"instance_url","label":"Instance URL","type":"url","required":true,"placeholder":"https://yourorg.salesforce.com"},{"name":"client_id","label":"Client ID","type":"text","required":true},{"name":"client_secret","label":"Client Secret","type":"password","required":true}]', 'available'),
('HubSpot', 'crm', 'HubSpot', 'Marketing automation, lead scoring, and customer lifecycle management integration.', 'users',
 '[{"name":"api_key","label":"API Key","type":"password","required":true},{"name":"portal_id","label":"Portal ID","type":"text","required":true}]', 'available'),
('Twilio', 'messaging', 'Twilio', 'Send offer notifications via SMS. Integrates with consent-based marketing (ePrivacy compliance).', 'message',
 '[{"name":"account_sid","label":"Account SID","type":"text","required":true},{"name":"auth_token","label":"Auth Token","type":"password","required":true},{"name":"from_number","label":"From Number","type":"tel","required":true,"placeholder":"+40..."}]', 'available'),
('SendGrid', 'messaging', 'Twilio SendGrid', 'Transactional and marketing email delivery for offer notifications and form confirmations.', 'message',
 '[{"name":"api_key","label":"API Key","type":"password","required":true},{"name":"from_email","label":"From Email","type":"email","required":true,"placeholder":"noreply@bankofferai.com"}]', 'available'),
('Stripe', 'payments', 'Stripe', 'Payment processing for premium product subscriptions and fee collection.', 'card',
 '[{"name":"publishable_key","label":"Publishable Key","type":"text","required":true,"placeholder":"pk_..."},{"name":"secret_key","label":"Secret Key","type":"password","required":true,"placeholder":"sk_..."},{"name":"webhook_secret","label":"Webhook Secret","type":"password","required":false}]', 'available'),
('OPA (Open Policy Agent)', 'security', 'Styra', 'Policy-as-code engine for authorization, compliance rules, and offer eligibility gating.', 'shield',
 '[{"name":"opa_url","label":"OPA Server URL","type":"url","required":true,"placeholder":"http://opa:8181"},{"name":"policy_path","label":"Policy Path","type":"text","required":true,"placeholder":"/v1/data/bankofferai/allow"}]', 'available');

-- ===== Central audit log (every state-changing action) =====

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    action VARCHAR(50) NOT NULL CHECK (action IN (
        'login','login_failed','logout',
        'create','update','delete',
        'approve','reject','implement','toggle',
        'activate','deactivate','revoke',
        'consent_change','kill_switch_toggle',
        'ai_analysis','export','override'
    )),
    actor VARCHAR(200) NOT NULL,                   -- staff email or customer_id
    actor_type VARCHAR(20) NOT NULL DEFAULT 'staff' CHECK (actor_type IN ('staff','customer','system','api_token')),
    resource_type VARCHAR(50) NOT NULL,            -- e.g. product, connector, suggestion, consent, kill_switch
    resource_id VARCHAR(200),                      -- the ID of the affected resource
    changes JSONB DEFAULT '{}',                    -- before/after diff or action details
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(200),                         -- API path, e.g. PUT /intelligence/suggestions/7/approve
    http_method VARCHAR(10),
    http_status INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- ===== AI API call log (every LLM provider interaction) =====

CREATE TABLE ai_api_call_log (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    provider VARCHAR(100) NOT NULL,                -- Anthropic, OpenAI, Google, etc.
    model VARCHAR(200) NOT NULL,
    endpoint_url VARCHAR(500),
    request_prompt TEXT,                            -- truncated system+user prompt
    request_tokens INTEGER,
    response_text TEXT,                             -- truncated response
    response_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    http_status INTEGER,
    outcome VARCHAR(20) NOT NULL DEFAULT 'success' CHECK (outcome IN ('success','failure','timeout','filtered','rate_limited')),
    guardrail_action VARCHAR(50),                  -- e.g. confidence_rejected, content_filtered, accepted
    guardrail_details JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- ===== Consent change history (append-only, GDPR Art. 7(1) proof) =====

CREATE TABLE consent_history (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    consent_type VARCHAR(50) NOT NULL CHECK (consent_type IN (
        'profiling_consent','automated_decision_consent',
        'family_context_consent','sensitive_data_consent',
        'marketing_push','marketing_email','marketing_sms'
    )),
    old_value BOOLEAN,
    new_value BOOLEAN NOT NULL,
    changed_by VARCHAR(200) NOT NULL,              -- staff email, customer_id, or 'system'
    change_reason TEXT,
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- ===== Immutability triggers =====

-- Guardrail #9: Audit log immutability (prevent UPDATE/DELETE) =====

CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '% is immutable — UPDATE and DELETE are prohibited (AI Act Art. 12 & 17)', TG_TABLE_NAME;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_immutable ON audit_recommendations;
CREATE TRIGGER audit_immutable
    BEFORE UPDATE OR DELETE ON audit_recommendations
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;
CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

DROP TRIGGER IF EXISTS ai_api_call_log_immutable ON ai_api_call_log;
CREATE TRIGGER ai_api_call_log_immutable
    BEFORE UPDATE OR DELETE ON ai_api_call_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

DROP TRIGGER IF EXISTS consent_history_immutable ON consent_history;
CREATE TRIGGER consent_history_immutable
    BEFORE UPDATE OR DELETE ON consent_history
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

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
