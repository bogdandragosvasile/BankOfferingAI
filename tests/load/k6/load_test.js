/**
 * k6 load test — GET /offers/{customer_id}
 *
 * Target:  500 RPS sustained for 60 seconds
 * SLO:     p99 response time < 300 ms, error rate < 1%
 *
 * Usage:
 *   k6 run load_test.js
 *   k6 run --env BASE_URL=https://api.bankoffer.example.com \
 *           --env AUTH_TOKEN=<jwt> load_test.js
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------

const errorRate = new Rate("errors");
const offerLatency = new Trend("offer_latency_ms", true);
const successCount = new Counter("successful_requests");

// ---------------------------------------------------------------------------
// Test configuration
// ---------------------------------------------------------------------------

export const options = {
  scenarios: {
    ramp_up: {
      executor: "ramping-arrival-rate",
      startRate: 0,
      timeUnit: "1s",
      preAllocatedVUs: 100,
      maxVUs: 700,
      stages: [
        { target: 500, duration: "15s" },  // ramp up to 500 RPS over 15s
        { target: 500, duration: "60s" },  // hold 500 RPS for 60s
        { target: 0,   duration: "10s" },  // ramp down
      ],
    },
  },
  thresholds: {
    // Primary SLO: p99 latency under 300 ms
    http_req_duration: ["p(99)<300"],
    // Custom trend also enforces p99
    offer_latency_ms: ["p(99)<300", "p(95)<200"],
    // Error rate must stay below 1%
    errors: ["rate<0.01"],
    // All HTTP calls should succeed
    http_req_failed: ["rate<0.01"],
  },
};

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const AUTH_TOKEN = __ENV.AUTH_TOKEN || "test-load-bearer-token";

// Pool of synthetic customer IDs to distribute load
const CUSTOMER_IDS = Array.from(
  { length: 200 },
  (_, i) => `cust_${String(i + 1).padStart(4, "0")}`
);

// ---------------------------------------------------------------------------
// Setup — runs once before the test
// ---------------------------------------------------------------------------

export function setup() {
  console.log(`BankOffer AI load test starting`);
  console.log(`  Target URL : ${BASE_URL}`);
  console.log(`  Scenario   : ramp 0→500 RPS over 15s, hold 60s, ramp down`);
  console.log(`  Threshold  : p99 < 300 ms, error rate < 1%`);

  // Warm-up: verify the API is reachable before ramping
  const warmup = http.get(`${BASE_URL}/health`);
  if (warmup.status !== 200) {
    console.warn(`Health check returned ${warmup.status} — proceeding anyway`);
  }
}

// ---------------------------------------------------------------------------
// Default function — runs per VU iteration
// ---------------------------------------------------------------------------

export default function () {
  // Pick a random customer from the pool
  const customerId =
    CUSTOMER_IDS[Math.floor(Math.random() * CUSTOMER_IDS.length)];

  const params = {
    headers: {
      Authorization: `Bearer ${AUTH_TOKEN}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    timeout: "5s",
    tags: { endpoint: "get_offers", customer_bucket: customerId.slice(-2) },
  };

  const start = Date.now();
  const res = http.get(`${BASE_URL}/offers/${customerId}`, params);
  const duration = Date.now() - start;

  offerLatency.add(duration);

  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "response has offers array": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.offers);
      } catch {
        return false;
      }
    },
    "response time < 300ms": (r) => r.timings.duration < 300,
    "content-type is JSON": (r) =>
      (r.headers["Content-Type"] || "").includes("application/json"),
  });

  errorRate.add(!ok);
  if (ok) {
    successCount.add(1);
  }

  // Minimal think-time to avoid spinning too fast on very fast responses
  sleep(0.001);
}

// ---------------------------------------------------------------------------
// Teardown — runs once after all VUs finish
// ---------------------------------------------------------------------------

export function teardown(data) {
  console.log("Load test complete");
  console.log(`  Check the summary above for p99 latency and error rate.`);
}
