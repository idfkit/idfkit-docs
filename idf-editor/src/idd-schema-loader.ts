/**
 * IDD Schema Loader
 *
 * Fetches and caches the compact IDD schema JSON for hover documentation.
 * The schema is loaded lazily from assets/idd-schema.json relative to the
 * current page.
 */

import type { CompactIDDSchema } from './types';

/** Cached schema instance */
let cachedSchema: CompactIDDSchema | null = null;

/** Whether a fetch is in progress */
let fetchPromise: Promise<CompactIDDSchema | null> | null = null;

/**
 * Get the IDD schema, loading it if necessary.
 *
 * Returns null if the schema hasn't been loaded yet or if loading failed.
 * The schema is fetched once per session and cached.
 */
export function getSchema(): CompactIDDSchema | null {
  return cachedSchema;
}

/**
 * Load the IDD schema from the assets directory.
 *
 * The schema JSON is expected at assets/idd-schema.json relative to
 * the current page's base URL. If loading fails (e.g., the schema
 * doesn't exist for older versions), hover docs simply won't be available.
 */
export async function loadSchema(): Promise<CompactIDDSchema | null> {
  if (cachedSchema) return cachedSchema;
  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    try {
      // Resolve the schema URL relative to the current page
      const schemaUrl = resolveSchemaUrl();
      const response = await fetch(schemaUrl);
      if (!response.ok) {
        console.debug(`[idf-editor] IDD schema not available (${response.status}), hover docs disabled`);
        return null;
      }
      cachedSchema = (await response.json()) as CompactIDDSchema;
      console.debug(`[idf-editor] IDD schema loaded: ${cachedSchema.version}`);
      return cachedSchema;
    } catch (error) {
      console.debug('[idf-editor] Failed to load IDD schema:', error);
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

/**
 * Clear the cached schema (used when navigating between versions).
 */
export function clearSchema(): void {
  cachedSchema = null;
  fetchPromise = null;
}

/**
 * Resolve the URL for the IDD schema JSON.
 *
 * The schema lives alongside the idf-editor.js script in the assets/ directory.
 * We derive the URL from the script's own src attribute so it works regardless
 * of the current page path (deep links, multi-version deployment, etc.).
 */
function resolveSchemaUrl(): string {
  // Find our own script tag and resolve relative to it
  const script = document.querySelector('script[src*="idf-editor"]');
  if (script) {
    const scriptSrc = (script as HTMLScriptElement).src;
    return new URL('idd-schema.json', scriptSrc).href;
  }
  // Fallback: absolute path from site root
  return new URL('/assets/idd-schema.json', window.location.origin).href;
}
