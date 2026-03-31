-- BankOfferAI database schema (with compliance tables)
-- Drop order respects FK dependencies
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
    -- GDPR Consent (Requirement 5)
    profiling_consent BOOLEAN DEFAULT FALSE,
    profiling_consent_ts TIMESTAMP,
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
