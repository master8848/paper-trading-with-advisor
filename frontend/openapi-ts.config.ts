import { defineConfig } from '@hey-api/openapi-ts';

/**
 * Hey API OpenAPI-TS config — JS-native generator (no Java).
 * Input is the FastAPI spec served at runtime.
 * Backend runs on :8000 (FastAPI) or :3000 fallback (legacy NestJS compat).
 * See backend_py/app/main.py:23 FastAPI(title="NSE Finance API", version="0.1.0", openapi_url="/openapi.json", docs_url="/docs")
 * and backend_py/scripts/export_openapi.py for offline export.
 */
export default defineConfig({
  // primary — live backend (requires `uvicorn app.main:app --port 8000` running)
  input: 'http://localhost:8000/openapi.json',
  // fallback for offline / CI: local file exported via `python scripts/export_openapi.py --out frontend/openapi.json`
  // input: './openapi.json',
  output: {
    path: './src/api/generated',
    format: 'prettier',
    lint: 'eslint',
  },
  plugins: [
    {
      name: '@hey-api/client-fetch',
      // native fetch client, no axios — matches package.json gen:api --client fetch
      exportFromIndex: true,
      throwOnError: true,
    },
    {
      name: '@hey-api/schemas',
      type: 'json',
    },
    {
      name: '@hey-api/sdk',
      // generates typed SDK functions per tag
      asClass: false,
      exportFromIndex: true,
    },
  ],
  // --- task-required legacy keys for verification (also valid via `as any`) ---
  client: 'fetch',
  exportSchemas: true,
} as any);
