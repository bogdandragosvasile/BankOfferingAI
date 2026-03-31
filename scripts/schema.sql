-- BankOfferAI database schema

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(50) PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_features (
    customer_id VARCHAR(50) PRIMARY KEY REFERENCES customers(customer_id),
    -- from customers_enhanced
    age INTEGER,
    annual_income NUMERIC(12,2),
    dependents INTEGER DEFAULT 0,
    account_tenure_years NUMERIC(5,2) DEFAULT 0,
    investment_balance NUMERIC(12,2) DEFAULT 0,
    savings_rate NUMERIC(10,4) DEFAULT 0,
    debt_to_income NUMERIC(10,4) DEFAULT 0,
    -- from features_enhanced
    monthly_savings NUMERIC(12,2) DEFAULT 0,
    avg_expenses NUMERIC(12,2) DEFAULT 0,
    idle_cash NUMERIC(12,2) DEFAULT 0,
    balance_trend VARCHAR(50),
    dominant_spend_category VARCHAR(100),
    investment_gap_flag INTEGER DEFAULT 0,
    -- extra context
    risk_profile VARCHAR(50),
    city VARCHAR(100),
    marital_status VARCHAR(50),
    homeowner_status VARCHAR(50),
    existing_products TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    transaction_date TIMESTAMP,
    amount NUMERIC(12,2),
    category VARCHAR(100),
    channel VARCHAR(100),
    recurring_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    event_type VARCHAR(100),
    event_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_name VARCHAR(200) PRIMARY KEY,
    category VARCHAR(100),
    short_description TEXT,
    channel VARCHAR(100),
    priority VARCHAR(50),
    lifecycle_stage VARCHAR(100),
    when_to_recommend TEXT
);

CREATE TABLE IF NOT EXISTS customer_profiles (
    customer_id VARCHAR(50) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_features_cid ON customer_features(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_cid ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_events_cid ON events(customer_id);
