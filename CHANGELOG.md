# Changelog

All notable changes to BankOffer AI are documented in this file.

## [2.4.0] — 2026-04-01

### Added

- **Full AI-to-Customer pipeline.** Approved AI product suggestions can now be published to the
  live product catalog and automatically scored against customer profiles:
  - **"Publish to Catalog"** button on approved suggestions inserts into the `products` table
  - Products become immediately active in the offer engine (no restart needed)
  - Generic scoring rules for AI-generated products: scored by `product_type` and `risk_level`
    with personalized boosts (idle cash, risk appetite, balance trend, family context, etc.)
  - `PUT /intelligence/suggestions/{id}/implement` endpoint with full validation
  - Implemented suggestions show "Live in catalog" status badge
  - MiFID II suitability and AI Act compliance checks apply equally to AI-generated products
- **Real AI provider integration.** Connected AI models now call real APIs:
  - Anthropic Claude, OpenAI GPT, Google Gemini, Hugging Face, **Perplexity AI**
  - **Local LLM** support: Ollama, vLLM, LM Studio (any OpenAI-compatible endpoint)
  - Falls back to built-in engine when no API key is configured
  - Validates and sanitizes all AI-generated data before DB insert

---

## [2.3.0] — 2026-04-01

### Added

- **Market Intelligence Hub.** AI-powered market analysis and product suggestion engine in the Admin portal:
  - 5 intelligence categories: Exchange Markets, Geopolitics, Regulations, Economic Indicators, Trends
  - 16 real-time market intelligence signals with impact/severity scoring and structured data points
  - 7 AI-generated product suggestions (savings, investment, lending, mortgage, credit) with confidence scores,
    target segments, market drivers, projected demand, and risk levels
  - **Run AI Analysis** button triggers full refresh — detects active AI connectors from the Connectors module
  - Admin approve/reject workflow for product suggestions
  - Expandable AI reasoning explaining why each product was recommended
  - Category filter tabs, summary stats dashboard, connected model indicator badge
  - `market_intelligence` and `ai_product_suggestions` database tables
  - `/intelligence/*` API router (market-data, analyze, suggestions CRUD, approve/reject)
  - Integrates with Connectors — uses active AI connector name as the model attribution

---

## [2.2.0] — 2026-04-01

### Added

- **Connectors Menu.** Admin portal now manages third-party service integrations:
  - 8 categories: AI, Cloud, Advertising, Analytics, CRM, Messaging, Payments, Security
  - 18 pre-seeded connector templates (OpenAI, Claude, AWS, Azure, GCP, Google Ads, Meta,
    LinkedIn, GA4, Mixpanel, Salesforce, HubSpot, Twilio, SendGrid, Stripe, OPA)
  - **AI Suggest** button — AI recommends connectors based on platform needs (pending admin approval)
  - Approval workflow: available → pending → approved → active (admin-gated)
  - Configuration modal with dynamic field rendering (text, password, select, textarea)
  - Category filter tabs with active/pending/total status counters
  - `/connectors/*` API router (list, create, configure, approve/reject, toggle, delete, AI suggest)

### Commit History

- `ed453f6` feat: add Connectors Menu for third-party service integrations

---

## [2.1.0] — 2026-04-01

### Added

- **Employee ↔ Customer workflow.** Full-cycle offer acceptance → notification → form → submission:
  - `notifications` and `application_forms` database tables
  - `/workflow/*` API router: notification CRUD, form lifecycle (create, list, submit)
  - Auto-create employee notification when customer accepts/rejects an offer
  - **Employee portal**: notification bell with unread badge (polls every 15s), dropdown panel,
    "Send Form" button with template selection (Standard, Investment, Loan, Insurance)
  - **Customer portal**: "My Forms" navigation tab, form rendering with field types
    (text, number, date, checkbox, textarea), submission flow
  - Form submission triggers a back-notification to the employee

### Commit History

- `fc8a0a1` feat: implement Employee ↔ Customer workflow (notifications + forms)

---

## [2.0.0] — 2026-04-01

### Changed

- **Unified design system across all portals.** Employee, Customer, and Admin portals now
  share the same CSS token system and design language as the presentation:
  - `:root` CSS custom properties for all colors, shadows, and focus rings
  - `[data-theme="light"]` overrides with WCAG-friendly contrast (#0f172a text, #f1f5f9 bg)
  - Reduced decoration: backdrop blur 20px→12px, toned-down glow/shadow effects
  - Score bar gradient updated to navy palette (#1e3a8a → #3b82f6)
  - Glass card hover effects softened (translateY -1px, lighter shadows)
  - Accessibility: `focus-visible` outline ring, `prefers-reduced-motion` media query

### Commit History

- `e1ef91d` feat: apply presentation design system to all three portals

---

## [1.9.0] — 2026-04-01

### Changed

- **Final presentation polish** — boardroom-ready refinements:
  - New `.card-supporting` variant for secondary content (stats, summaries, SDLC cards)
  - Team slide badge clusters replaced with compact dot-separated text
  - Light theme: `--text-muted` contrast improved to #475569, gradient-text override added
  - Flow-step numbers reduced to 40px to reduce visual competition
  - Paragraph max-width capped at 65ch for readability
  - Architecture diagram padding for breathing room
  - Slide counter border-radius matched to theme toggle (10px)
  - h3 margin-bottom added for consistent card heading spacing

### Commit History

- `718fd19` feat: final polish pass — boardroom-ready presentation

---

## [1.8.0] — 2026-04-01

### Changed

- **Presentation second-pass refinement** — 14 executive-grade design improvements:
  - Proper CSS token system (`--card-bg`, `--text-primary`, `--accent-subtle`, etc.)
    with both dark and light themes sharing the same design language
  - WCAG-friendly contrast in both themes, no pure black/white
  - Refined theme toggle with `aria-label`, focus-visible ring, enterprise styling
  - Reduced decoration: removed card-glow, SVG glow filter, toned down pulse animation
  - Tighter typographic hierarchy: calmer h2, smaller subtitles, understated labels
  - Left-aligned explanatory content across non-hero slides
  - Badge clusters in onboarding slide replaced with compact middle-dot text
  - CTA hierarchy: single primary button + secondary text link pattern
  - Layout breathing room: 2-column stat row, whitespace after audit table
  - Enterprise card design: 12px radius, token-based shadows, subtle hover
  - Em-dash list bullets replacing triangles for executive readability
  - Slimmer slide counter (36px, 0.8rem) with navigation role
  - Semantic HTML: `<main>` wrapper, aria-labels, reduced-motion media query

### Commit History

- `5aa5324` feat: second-pass presentation refinement for executive fintech audience

---

## [1.7.0] — 2026-04-01

### Changed

- **Unified design system across all portals.** Employee, Customer, and Admin portals now
  use the same navy palette and Cabinet Grotesk display font as the presentation:
  deep navy (#1e3a8a), blue (#3b82f6), deep green (#047857), gold (#d97706).

### Commit History

- `0af46bd` feat: apply navy palette and Cabinet Grotesk font to all three portals

---

## [1.6.0] — 2026-04-01

### Fixed

- **Login always skips onboarding wizard.** The previous `last_login` heuristic failed for
  seeded demo users (who have `last_login=NULL`). Login and SSO endpoints now unconditionally
  return `onboarding_complete=true` and auto-update the database. Only `/register` routes
  new users through the wizard.

### Restored

- **Light/dark theme toggle** on the presentation, removed by mistake in v1.5.0.

### Commit History

- `c3e8d98` fix: login always skips onboarding wizard, restore theme toggle

---

## [1.5.0] — 2026-04-01

### Changed

- **Presentation redesign** — 12 UX fixes from design critique:
  - New color palette: deep navy (#1e3a8a), blue (#3b82f6), deep green (#047857), gold (#d97706)
  - Cabinet Grotesk display font for headings
  - Single navy→blue gradient-text class (removed green/purple/amber variants)
  - Slide counter navigation replaces pill dots
  - Left-aligned content on all non-hero slides
  - Layout variety: 2-column portals, 2×2 flow steps, 2-column compliance
  - Badges replaced with icon lists on portal cards
  - Focused CTA: single primary button + secondary link on demo slide
  - Removed light mode toggle and bg-glow background effects
  - Icon circles reduced to 32px natural size without backgrounds
  - 44px minimum touch targets on navigation
- Updated footer version to v1.4.0

### Commit History

- `2bc1e43` feat: redesign presentation with navy palette, Cabinet Grotesk font, and 12 UX fixes

---

## [1.4.0] — 2026-04-01

### Fixed

- **Existing users no longer see the onboarding wizard on login.** The `onboarding_complete`
  column (added with `DEFAULT FALSE`) caused all pre-existing customers to be routed into the
  registration wizard. Login and SSO endpoints now detect returning users via `last_login` and
  auto-complete their onboarding status.
- **Frontend session flag tightened** from `!== false` to `=== true` in `saveCustomerSession()`
  to prevent falsy values (`null`, `undefined`) from being treated as onboarding-complete.
- **Consent blocks panel** no longer shows `0` instead of a no-data state when there are no
  consent entries.

### Changed

- Updated Oana Sarlea's role from "Product Owner" to "BizTech Consultant Financial Services"
  in the presentation.

### Commit History

- `d633402` fix: skip onboarding wizard for existing users on login
- `cee949e` fix: consent blocks panel shows 0 instead of no-data

---

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
