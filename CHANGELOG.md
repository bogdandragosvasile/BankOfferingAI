# Changelog

All notable changes to BankOffer AI are documented in this file.

## [1.1.0] — 2026-04-01

### Breaking Changes

- **Customer registration creates new records instead of reusing existing ones.**
  `POST /customer-auth/register` now creates a fresh `customers` + `customer_features` row
  with an auto-increment integer ID (51, 52, ...) instead of assigning a random existing
  profile. Clients relying on the old behavior (where registration returned a pre-seeded
  customer ID 1–50) must be updated.

- **Registration and login responses include `onboarding_complete` field.**
  `CustomerRegisterResponse` and `CustomerLoginResponse` now return `onboarding_complete: bool`.
  API consumers parsing these responses strictly will need to handle the new field.

- **SSO lookup response includes `onboarding_complete` field.**
  `GET /customer-auth/sso-lookup` now returns `onboarding_complete` in the response body.

- **Employee portal customer list is now dynamic.**
  The employee portal (`/`) no longer hardcodes customer IDs 1–50. It fetches the full list
  from `GET /customer-auth/customers/list`. Deployments without this endpoint fall back to 1–50.

- **Offers endpoint loads products from database at request time.**
  `GET /offers/{customer_id}` now queries the `products` table for active products instead of
  using a hardcoded product list. Falls back to built-in defaults if the DB query fails.

### Added

- **Customer onboarding wizard** — 3-step wizard (consent, profile questionnaire, review)
  shown to newly registered customers. Collects GDPR/AI Act consent and profile data
  (age, income, risk tolerance, employment, homeowner status, existing products).
  Generates a computed profile via `build_profile()` on completion.
  - `PUT /customer-auth/onboarding/{customer_id}` — submit wizard data
  - `GET /customer-auth/onboarding/status/{customer_id}` — check completion status
  - `GET /customer-auth/customers/list` — list all customer IDs

- **Product catalog CRUD** — Full product management via admin portal and API.
  - `GET /products-catalog/` — list all products
  - `GET /products-catalog/{id}` — get single product
  - `POST /products-catalog/` — create product
  - `PUT /products-catalog/{id}` — update product
  - `DELETE /products-catalog/{id}` — delete product

- **Consent registry with periodic sync** — Loads consent checkbox definitions from
  `Consent_Checkbox_Texts_Audit_Ready 1.xlsx` into 5 database tables. Background task
  syncs every 6 hours using SHA-256 file hashing to detect changes. Version
  auto-increments only on actual modifications.
  - `GET /consent-registry/sync-status` — current sync state
  - `POST /consent-registry/sync` — trigger manual sync
  - `GET /consent-registry/texts` — official consent texts
  - `GET /consent-registry/product-map` — product–consent matrix
  - `GET /consent-registry/ai-rules` — AI consent rules
  - `GET /consent-registry/implementation-map` — implementation mappings
  - `GET /consent-registry/sources` — regulatory sources

- **Regulatory source change detection** — Background task (every 24h) fetches EUR-Lex
  URLs from the consent registry sources, computes SHA-256 of page content, and flags
  changes for admin review. Red alert banner in admin portal.
  - `POST /consent-registry/check-sources` — trigger manual check
  - `GET /consent-registry/source-checks` — check results
  - `POST /consent-registry/source-checks/{id}/review` — dismiss alert

- **API token management** — Programmatic access tokens with scopes, expiry, and
  revocation. Admin portal UI for token lifecycle management.
  - `POST /api-tokens/` — create token
  - `GET /api-tokens/` — list tokens
  - `DELETE /api-tokens/{id}` — revoke token

- **Internationalization** — Full i18n support (EN, DE, RO) for product catalog,
  consent registry, onboarding wizard, and offer content (product names, types,
  personalization explanations).

- **Portal navigation bar** on all three login screens (employee, customer, admin).
- **Mobile-responsive layout** for all three portals.

### Fixed

- SSO login now resolves `customer_id` from database instead of using a fallback.
- Schema uses `IF NOT EXISTS` for `api_tokens` indexes to prevent migration errors.
- Regulatory source initial false positives documented (EUR-Lex dynamic HTML elements).
- Onboarding data written to both `customers` and `customer_features` tables.
- My Data tab renders partial data when full profile is not yet available.
- Consent registry texts collapsed into expandable section in onboarding wizard.

### Commit History

- `2a65681` fix: collapse regulatory consent texts into expandable section
- `cdaca9b` fix: populate customers table + generate profile during onboarding
- `388f05c` feat: add customer onboarding wizard with consent + profile questionnaire
- `8ec70f7` feat: add regulatory source change detection with periodic URL monitoring
- `5feeefb` feat: add consent registry with periodic sync from audit workbook
- `5c430e8` feat: add product catalog CRUD API and admin portal UI
- `422204e` feat: mobile-responsive layout for all three portals
- `8f36ef6` fix: use IF NOT EXISTS for api_tokens indexes in schema.sql
- `cd79526` feat: add portal navigation bar to all login screens
- `dcb3f5d` feat: add API token management to admin portal
- `ac7c46f` feat: translate offer content (product names, types, explanations) in DE/RO
- `d6eb4e5` fix: resolve customer_id from database for SSO portal login
- `361b2c4` docs: add server DB_PASSWORD reference to .env

---

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
