/// <reference types="cypress" />

/**
 * BankOffer AI — Dashboard E2E smoke tests
 *
 * Flow tested:
 *   1. Login with valid credentials
 *   2. View the personalised offers list on the dashboard
 *   3. Click the CTA button on the first offer
 *
 * Prerequisites:
 *   - Cypress env vars: BANK_EMAIL, BANK_PASSWORD (defaults provided)
 *   - The app must be running at the baseUrl configured in cypress.config.ts
 */

const EMAIL = Cypress.env("BANK_EMAIL") || "customer@bank.example.com";
const PASSWORD = Cypress.env("BANK_PASSWORD") || "SecurePass123!";

// ---------------------------------------------------------------------------
// Custom command types (defined in cypress/support/commands.ts)
// ---------------------------------------------------------------------------
declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Log in via the UI and wait for the dashboard to load.
       * @param email    Customer e-mail address
       * @param password Customer password
       */
      login(email: string, password: string): Chainable<void>;
    }
  }
}

// ---------------------------------------------------------------------------
// Helper: perform login through the UI
// ---------------------------------------------------------------------------

function login(email: string, password: string): void {
  cy.visit("/login");
  cy.get('[data-testid="email-input"]').should("be.visible").type(email);
  cy.get('[data-testid="password-input"]').should("be.visible").type(password);
  cy.get('[data-testid="login-btn"]').click();
  // Wait until the dashboard URL is active before continuing
  cy.url().should("include", "/dashboard");
}

// ---------------------------------------------------------------------------
// Smoke test suite
// ---------------------------------------------------------------------------

describe("BankOffer AI Dashboard — smoke tests", () => {
  beforeEach(() => {
    // Intercept API calls so tests don't depend on live data
    cy.intercept("POST", "/api/auth/login").as("loginRequest");
    cy.intercept("GET", "/api/offers/*").as("getOffers");
    cy.intercept("POST", "/api/offers/*/accept").as("acceptOffer");
    cy.intercept("POST", "/api/offers/*/dismiss").as("dismissOffer");
  });

  // -------------------------------------------------------------------------
  // 1. Login
  // -------------------------------------------------------------------------

  context("Login flow", () => {
    it("redirects unauthenticated users to /login", () => {
      cy.visit("/dashboard");
      cy.url().should("include", "/login");
    });

    it("logs in with valid credentials and lands on dashboard", () => {
      cy.visit("/login");
      cy.get('[data-testid="email-input"]').type(EMAIL);
      cy.get('[data-testid="password-input"]').type(PASSWORD);
      cy.get('[data-testid="login-btn"]').click();

      cy.wait("@loginRequest").its("response.statusCode").should("eq", 200);
      cy.url().should("include", "/dashboard");
    });

    it("shows an error message for invalid credentials", () => {
      cy.visit("/login");
      cy.get('[data-testid="email-input"]').type("wrong@example.com");
      cy.get('[data-testid="password-input"]').type("wrongpassword");
      cy.get('[data-testid="login-btn"]').click();

      cy.get('[data-testid="error-message"]').should("be.visible");
      cy.url().should("include", "/login");
    });
  });

  // -------------------------------------------------------------------------
  // 2. View offers list
  // -------------------------------------------------------------------------

  context("Offers list", () => {
    beforeEach(() => {
      login(EMAIL, PASSWORD);
      cy.wait("@getOffers");
    });

    it("displays the personalised offers section header", () => {
      cy.get('[data-testid="dashboard-header"]').should("be.visible");
      cy.contains("Your Personalized Offers").should("be.visible");
    });

    it("renders at least one offer card", () => {
      cy.get('[data-testid="offer-card"]').should("have.length.at.least", 1);
    });

    it("each offer card shows product name, personalisation reason, confidence badge, and CTA button", () => {
      cy.get('[data-testid="offer-card"]')
        .first()
        .within(() => {
          cy.get('[data-testid="product-name"]').should("be.visible");
          cy.get('[data-testid="personalization-reason"]').should("be.visible");
          cy.get('[data-testid="confidence-badge"]').should("be.visible");
          cy.get('[data-testid="cta-button"]').should("be.visible");
        });
    });

    it("displays the notification bell icon", () => {
      cy.get('[data-testid="notification-bell"]').should("be.visible");
    });
  });

  // -------------------------------------------------------------------------
  // 3. Click CTA on first offer
  // -------------------------------------------------------------------------

  context("CTA interaction on first offer", () => {
    beforeEach(() => {
      login(EMAIL, PASSWORD);
      cy.wait("@getOffers");
    });

    it("navigates to the offer detail page when the CTA is clicked", () => {
      cy.get('[data-testid="offer-card"]')
        .first()
        .find('[data-testid="cta-button"]')
        .click();

      // The URL should match /offers/<some-id>
      cy.url().should("match", /\/offers\/.+/);
    });

    it("shows the offer detail page after CTA click", () => {
      cy.get('[data-testid="offer-card"]')
        .first()
        .find('[data-testid="cta-button"]')
        .click();

      // Offer detail should surface an accept button
      cy.get('[data-testid="accept-offer-btn"]').should("be.visible");
    });

    it("allows accepting the offer from the detail page", () => {
      cy.get('[data-testid="offer-card"]')
        .first()
        .find('[data-testid="cta-button"]')
        .click();

      cy.get('[data-testid="accept-offer-btn"]').click();
      cy.wait("@acceptOffer").its("response.statusCode").should("eq", 200);
      cy.get('[data-testid="success-message"]').should("be.visible");
    });

    it("allows dismissing an offer from the list", () => {
      cy.get('[data-testid="offer-card"]').then(($cards) => {
        const initialCount = $cards.length;
        cy.get('[data-testid="offer-card"]')
          .first()
          .find('[data-testid="dismiss-btn"]')
          .click();
        cy.wait("@dismissOffer");
        cy.get('[data-testid="offer-card"]').should(
          "have.length.lessThan",
          initialCount
        );
      });
    });
  });

  // -------------------------------------------------------------------------
  // 4. Notification flow
  // -------------------------------------------------------------------------

  context("Notification panel", () => {
    beforeEach(() => {
      login(EMAIL, PASSWORD);
    });

    it("opens the notification dropdown when the bell is clicked", () => {
      cy.get('[data-testid="notification-bell"]').click();
      cy.get('[data-testid="notification-dropdown"]').should("be.visible");
    });

    it("marks all notifications as read", () => {
      cy.get('[data-testid="notification-bell"]').click();
      cy.get('[data-testid="mark-all-read-btn"]').click();
      cy.get('[data-testid="notification-item"].unread').should("not.exist");
    });
  });
});
