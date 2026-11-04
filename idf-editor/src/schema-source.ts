/**
 * Schema source for hover documentation.
 *
 * Schemas and the documentation prose pool come from the published
 * `@idfkit/schemas` package, served by jsDelivr at the exact version this
 * bundle was built against (the same CDN Monaco is loaded from). One
 * `SchemaBundle` serves every EnergyPlus version, and the browser caches the
 * shared blob store across every version of this site.
 *
 * The EnergyPlus version of the current page is read from the
 * `idfkit:energyplus-version` meta tag that `scripts/convert.py` writes into
 * each per-version site.
 */

import { SchemaBundle, httpSource, type ProsePool, type Schema } from '@idfkit/schemas';

declare const __IDFKIT_SCHEMAS_VERSION__: string;

/** Base URL of the schema data files for the pinned package version. */
const SCHEMA_DATA_URL = `https://cdn.jsdelivr.net/npm/@idfkit/schemas@${__IDFKIT_SCHEMAS_VERSION__}/data/`;

/** Meta tag carrying the page's EnergyPlus version, e.g. "25.2.0". */
const VERSION_META = 'idfkit:energyplus-version';

const bundle = new SchemaBundle(httpSource(SCHEMA_DATA_URL));

/** The EnergyPlus version this page documents, or `undefined` when not declared. */
export function pageVersion(): string | undefined {
  const meta = document.querySelector<HTMLMetaElement>(`meta[name="${VERSION_META}"]`);
  const content = meta?.content.trim();
  return content ? content : undefined;
}

/** The schema for this page, if it has finished loading. Synchronous. */
export function currentSchema(): Schema | undefined {
  const version = pageVersion();
  return version === undefined ? undefined : bundle.loaded(version);
}

/** The prose pool, if it has finished loading. Synchronous. */
export function currentProse(): ProsePool | undefined {
  return bundle.prose();
}

/**
 * Start loading the page's schema and the prose pool in the background.
 *
 * Idempotent: the bundle shares one read between concurrent calls. A failure
 * leaves hover documentation unavailable and is reported to the console only,
 * because the code blocks remain fully readable without it.
 */
export function preloadSchema(): void {
  const version = pageVersion();
  if (version === undefined) {
    console.debug(`[idf-editor] No ${VERSION_META} meta tag; hover docs disabled`);
    return;
  }
  bundle.load(version).catch((error: unknown) => {
    console.debug(`[idf-editor] Schema ${version} unavailable; hover docs disabled:`, error);
  });
  bundle.loadProse().catch((error: unknown) => {
    console.debug('[idf-editor] Documentation prose unavailable:', error);
  });
}
