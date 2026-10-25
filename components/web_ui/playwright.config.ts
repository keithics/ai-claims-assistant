import { defineConfig } from "@playwright/test";

const uv = process.env.UV ?? "uv";
const claimsPort = 18001;
const apiPort = 18000;
const uiPort = 15173;
const signingKey = "e2e-signing-key-0123456789abcdef";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: `http://localhost:${uiPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `${uv} run --package claims_api uvicorn claims_api.app:create_app --factory --port ${claimsPort}`,
      cwd: "../..",
      url: `http://localhost:${claimsPort}/healthz`,
      reuseExistingServer: false,
      env: {
        APPROVAL_SIGNING_KEY: signingKey,
        CLAIMS_API_LATENCY_P50_MS: "20",
        CLAIMS_API_LATENCY_P95_MS: "40",
        CLAIMS_API_FAILURE_RATE: "0",
        CLAIMS_API_SEED: "1",
      },
    },
    {
      command: `${uv} run --package agent_app uvicorn agent_app.main:create_app --factory --port ${apiPort}`,
      cwd: "../..",
      url: `http://localhost:${apiPort}/healthz`,
      reuseExistingServer: false,
      env: {
        AGENT_FAKE_MODE: "1",
        APPROVAL_SIGNING_KEY: signingKey,
        CLAIMS_API_URL: `http://localhost:${claimsPort}`,
        AGENT_CORS_ORIGINS: `http://localhost:${uiPort}`,
      },
    },
    {
      command: `pnpm exec vite --port ${uiPort} --strictPort`,
      url: `http://localhost:${uiPort}`,
      reuseExistingServer: false,
    },
  ],
});
