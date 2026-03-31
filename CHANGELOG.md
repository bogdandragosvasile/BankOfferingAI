# Changelog

All notable changes to BankOffer AI are documented in this file.

## [1.0.0] — 2026-03-31

### Features
- **AI-Powered Offer Engine**: Real-time product scoring with XGBoost conversion-probability model, customer profiler, and offer ranker with business rules and diversity constraints
- **Three-Portal Architecture**: Admin portal (`/admin`), Employee portal (`/`), and Customer portal (`/portal`) with role-based access control
- **Keycloak SSO Integration**: Full OIDC authorization code flow with PKCE (S256) across all three portals, using manual token exchange for maximum compatibility
- **Dual Authentication**: SSO via Keycloak and email/password login available side-by-side on every portal
- **GDPR 5-Tier Consent System**: Granular consent management (essential, analytics, AI profiling, cross-sell, third-party sharing) with audit trail and data retention controls
- **EU AI Act Compliance**: Transparency notices, algorithmic explanation panels, human override (kill switch), bias monitoring dashboard, and model documentation
- **MiFID II Suitability Assessment**: Product suitability checks with risk acknowledgment before investment offers
- **EBA Guidelines Compliance**: Fair treatment validation, product governance documentation, and distribution controls
- **Customer Data Anonymization**: Email addresses stored as irreversible SHA-256 hashes, automatic anonymization after 2-year retention period (GDPR Art. 5(1)(e))
- **Internationalization (i18n)**: Full translations in English, German, and Romanian across all portals
- **Dark/Light Theme**: System-aware theme toggle with persistent preference
- **Real-Time Product Catalog**: Eligibility counts, product filtering, and customer-product matching
- **Offer Feedback Loop**: Customer feedback collection on offered products for model improvement
- **Staff Login System**: Email/password authentication for employees and admins with bcrypt password hashing
- **Customer Registration**: Self-service registration with GDPR consent collection
- **NeuroBank Dashboard UI**: Glass-morphism dark theme with responsive layout and animated transitions

### Infrastructure
- **Docker Compose Stack**: PostgreSQL 16, Redis 7, Keycloak 25 (local) / 26.2 (standalone), Nginx reverse proxy, FastAPI API server
- **Pangolin TLS Proxy**: TLS termination for `bankoffer.lupulup.com` and `auth.lupulup.com`
- **Standalone Keycloak Server**: Dedicated Keycloak 26.2 instance at `auth.lupulup.com` with realm `bankofferai`, 7 demo users, and role-based protocol mappers
- **Container Restart Policies**: All services configured with `unless-stopped` for VM reboot resilience
- **Database Seeding**: Automated seed script populating 50 customers, 14 financial products, transaction histories, and demo credentials
- **Health Checks**: PostgreSQL, Redis, and Keycloak health probes with configurable intervals

### Security
- **PKCE S256**: All SSO flows use Proof Key for Code Exchange with SHA-256 challenge
- **CORS Configuration**: Strict origin validation between app and Keycloak domains
- **Session Management**: 8-hour staff sessions, 24-hour customer sessions with automatic expiry
- **Token Refresh**: Automatic access token refresh before expiry
- **Password Hashing**: bcrypt for staff and customer passwords

### Demo Users

| Email | Password | Role | Portal |
|-------|----------|------|--------|
| admin@bankofferai.com | Admin1234! | admin | /admin |
| manager@bankofferai.com | Employee1234! | employee | / |
| demo@bankofferai.com | Demo1234! | client | /portal |
| maria.johnson@example.com | Customer1! | client | /portal |
| alex.chen@example.com | Customer1! | client | /portal |
| sarah.miller@example.com | Customer1! | client | /portal |
| john.doe@example.com | Customer1! | client | /portal |

### Deployment

| Host | IP | Service | URL |
|------|-----|---------|-----|
| App Server | 192.168.1.141 | API + Postgres + Redis + Nginx | https://bankoffer.lupulup.com |
| Keycloak | 192.168.1.190 | Keycloak 26.2 (standalone) | https://auth.lupulup.com |
| Pangolin | 192.168.1.161 | TLS reverse proxy | — |

### Commit History

- `f57b1c9` fix: point Keycloak admin links to auth.lupulup.com instead of relative /auth/
- `47218f7` feat: add SSO (Keycloak) login option to customer portal
- `0f9c486` fix: use id_token (not access_token) for Keycloak logout id_token_hint
- `f212e35` fix: replace keycloak-js adapter with manual PKCE auth code flow
- `f13aa38` fix: SSO callback not processed when stale demo session exists in localStorage
- `857afc2` fix: create Keycloak adapter at script load and init immediately
- `f3d4501` fix: make SSO button work reliably with fallback direct redirect
- `40f796f` feat: add Keycloak SSO login option to employee and admin portals
- `0b26674` fix: apply light theme background to login screens
- `44a7685` fix: remove duplicate customer badge from portal nav bar
- `651b2ec` feat: staff login for employee and admin portals with role-based redirect
- `99e7612` fix: center login screen with fixed positioning for proper viewport alignment
- `f985341` fix: add DROP TABLE IF EXISTS for customer_auth in schema.sql
- `e9dbb17` fix: rename /auth/customer to /customer-auth to avoid Pangolin /auth proxy conflict
- `04a12e4` feat: customer login/registration with automatic data anonymization
- `0873a3a` fix: show login screen on first visit and highlight active language
- `4e2613a` fix: redirect to correct portal after demo login role selection
- `ed52246` fix: make consent toggles more robust with event listeners and inline styles
- `27ee04f` fix: use numeric customer IDs in portal and fix consent overview
- `7aa135f` feat: real-time client eligibility counts on Product Catalog
- `5d6f677` feat: implement 5-tier GDPR consent system and EU AI Act compliance
- `719f6be` fix: complete i18n coverage — add missing Romanian admin keys, data-i18n attributes
- `a51dc20` fix: admin portal crash, complete i18n translations for all 3 portals
- `162459a` fix: use firstBrokerLoginFlowAlias instead of updateProfileFirstLoginFlow for Keycloak 25
- `194e044` feat: add Keycloak auth, admin portal, light theme, and i18n (EN/DE/RO)
- `c26eea9` fix: add customer_id to FeedbackRequest model
- `9a78807` fix: use CAST() instead of :: for asyncpg compatibility in audit queries
- `2a00776` feat: implement 6 compliance requirements + customer/employee portals
- `14ca3f5` feat: add multi-page navigation and clickable product catalog
- `85dfe69` fix: handle JSONB dict deserialization in profiles endpoint
- `2f51e2e` fix: profiles auth bypass + context-aware scoring engine
- `f8dc328` feat: add NeuroBank-style dark dashboard UI
- `26b601a` fix: skip seed rows referencing non-existent customer IDs
- `9485fd2` feat: standalone demo deployment with inline scoring
- `9b23e14` feat: full BankOffer AI implementation
- `bf4c232` fix: add Next.js entry points and mock login for local development
- `dc9c0cb` Add files via upload
- `03a49d6` fix: skip ArgoCD CD workflows when infrastructure not provisioned
- `90d9a0b` chore: initial repo scaffold
- `4c2dfd1` Initial commit
