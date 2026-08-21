/**
 * Thin fetch wrapper that the generated Hey API client uses.
 *
 * The generated `src/api/generated/client.gen.ts` exposes a `client` with `setConfig`.
 * This file provides:
 *  - `API_BASE` from Vite env (VITE_API_URL) with sensible fallback
 *  - `configureApiClient()` to wire the generated client to the correct baseUrl
 *  - `fetchWithBase()` — same semantics as `src/lib/api.ts:api()` for manual calls
 *
 * Usage:
 *   import { configureApiClient } from '@/api/client';
 *   configureApiClient(); // call once at app bootstrap (main.tsx)
 *
 *   // or use generated SDK directly:
 *   import { getStocks } from '@/api/generated';
 *   const data = await getStocks({ query: { duration: 'tweek' } });
 */

export const API_BASE =
  (import.meta as any).env?.VITE_API_URL ||
  (import.meta as any).env?.VITE_API_BASE ||
  'http://localhost:3000';

/**
 * Configure the Hey API generated client to use API_BASE.
 * Safe to call even if generated client not yet generated — no-op in that case.
 * Uses dynamic import so file type-checks before generation (run `npm run gen:api` first).
 */
export async function configureApiClient(baseUrl: string = API_BASE): Promise<void> {
  try {
    // @ts-ignore — generated client not present until `npm run gen:api`
    const mod: any = await import('./generated/client.gen');
    const c = mod?.client ?? mod?.default?.client ?? mod?.default;
    if (c?.setConfig) {
      c.setConfig({ baseUrl });
    }
  } catch {
    // generated client not yet present (run `npm run gen:api` first)
  }
}

// sync variant for bootstrap that cannot await — fire-and-forget
export function configureApiClientSync(baseUrl: string = API_BASE): void {
  void configureApiClient(baseUrl);
}

/**
 * Direct fetch wrapper — mirrors src/lib/api.ts:api() but exported here
 * for code that prefers to import from `@/api/client`.
 * Handles BASE prefix, JSON headers, auto-stringify, error unwrap, 204.
 */
export async function fetchWithBase<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const fullUrl =
    url.startsWith('http://') || url.startsWith('https://') ? url : `${API_BASE}${url}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((opts.headers as Record<string, string> | undefined) ?? {}),
  };

  let body: any = opts.body as any;
  if (
    body &&
    typeof body === 'object' &&
    !(body instanceof FormData) &&
    typeof body !== 'string'
  ) {
    body = JSON.stringify(body);
  }

  const res = await fetch(fullUrl, { ...opts, headers, body });

  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      msg = (errBody as any)?.detail || (errBody as any)?.message || JSON.stringify(errBody) || msg;
    } catch {
      try {
        msg = await res.text();
      } catch {}
    }
    throw new Error(msg);
  }

  if (res.status === 204) return undefined as T;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return (await res.json()) as T;
  try {
    return (await res.json()) as T;
  } catch {
    return (await res.text()) as unknown as T;
  }
}

export { fetchWithBase as apiFetch };

/** Re-export helper from lib/api for compatibility */
export { qs } from '@/lib/api';
