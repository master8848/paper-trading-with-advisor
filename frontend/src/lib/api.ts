export const BASE =
  (import.meta as any).env?.VITE_API_URL ||
  (import.meta as any).env?.VITE_API_BASE ||
  "http://localhost:8000";

/**
 * Thin fetch wrapper — native fetch with JSON handling.
 * - prepends BASE for relative URLs
 * - sets JSON content-type (merged with caller headers)
 * - stringifies body if plain object (not already string/FormData)
 * - throws on !ok with message from body
 * - returns parsed JSON as T (handles 204 no-content)
 */
export async function api<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const fullUrl = url.startsWith("http://") || url.startsWith("https://") ? url : `${BASE}${url}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> | undefined),
  };

  // auto-stringify plain object bodies
  let body = opts.body as any;
  if (body && typeof body === "object" && !(body instanceof FormData) && typeof body !== "string") {
    body = JSON.stringify(body);
  }

  const res = await fetch(fullUrl, {
    ...opts,
    headers,
    body,
  });

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

  // 204 or empty
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  // fallback: try json else text
  try {
    return (await res.json()) as T;
  } catch {
    return (await res.text()) as unknown as T;
  }
}

/** Build query string from plain object — skips undefined/null/empty. */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Generated client compatibility — Hey API (fetch, no axios)
// ---------------------------------------------------------------------------
/**
 * `src/lib/api.ts` is the hand-written wrapper used by existing code
 * (Home.tsx, PaperTradeForm.tsx before codegen). After running
 * `npm run gen:api`, a typed SDK is available at `src/api/generated`.
 *
 * Compatibility:
 *  - Existing `api<T>(url, init)` calls keep working — they already use
 *    native fetch and BASE from VITE_API_URL, same transport as the generated client.
 *  - New code should prefer the generated SDK:
 *      import { getStocks, createTrade } from '@/api/generated';
 *      // or via the thin wrapper that configures baseUrl:
 *      import { configureApiClient } from '@/api/client';
 *  - `BASE` is exported so callers can reuse it to configure the generated client:
 *      import { client } from '@/api/generated/client.gen';
 *      client.setConfig({ baseUrl: BASE });
 *
 * No axios — both layers use native fetch. Do not import `axios` in new code.
 * If you need typed calls before the SDK is generated, this file *is* the client.
 */
export const API_URL = BASE;

/**
 * Optional helper to initialize the generated Hey API client if it exists.
 * No-op before `npm run gen:api` has been run.
 */
export async function initGeneratedClient(baseUrl: string = BASE): Promise<void> {
  try {
    // @ts-ignore — generated SDK not present until `npm run gen:api`
    const mod: any = await import('@/api/generated/client.gen');
    const c = mod?.client ?? mod?.default?.client ?? mod?.default;
    if (c?.setConfig) c.setConfig({ baseUrl });
  } catch {
    // generated client not yet present — run `npm run gen:api`
  }
}
