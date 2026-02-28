/**
 * IDF Editor — Main Entry Point
 *
 * Scans documentation pages for IDF code blocks and progressively replaces
 * them with rich Monaco editor instances featuring syntax highlighting,
 * hover documentation, and code folding.
 *
 * Monaco is loaded lazily from CDN only when IDF code blocks are present.
 */

import './idf-editor.css';
import { EditorManager, loadMonacoFromCDN } from './editor-manager';
import { idfLanguageConfiguration, idfTokensProvider, IDF_LANGUAGE_ID } from './idf-language';
import { registerIDFThemes } from './idf-themes';
import { registerHoverProvider } from './idf-hover-service';
import { getSchema, loadSchema } from './idd-schema-loader';
import type * as Monaco from 'monaco-editor';

/** Whether the IDF language has been registered (once globally) */
let languageRegistered = false;

/** Current editor manager (recreated on each page navigation) */
let currentManager: EditorManager | null = null;

/** Whether initPage() is currently running (prevents concurrent execution) */
let initInProgress = false;

/**
 * Register the IDF language, themes, and providers with Monaco.
 * Only done once globally (Monaco language registration is persistent).
 */
function registerLanguage(monaco: typeof Monaco): void {
  if (languageRegistered) return;

  // Register language
  monaco.languages.register({
    id: IDF_LANGUAGE_ID,
    extensions: ['.idf', '.imf'],
    aliases: ['IDF', 'EnergyPlus IDF', 'Input Data File'],
    mimetypes: ['text/x-idf'],
  });
  monaco.languages.setLanguageConfiguration(IDF_LANGUAGE_ID, idfLanguageConfiguration);
  monaco.languages.setMonarchTokensProvider(IDF_LANGUAGE_ID, idfTokensProvider);

  // Register themes
  registerIDFThemes(monaco);

  // Register hover provider (schema may not be loaded yet; getSchema returns null until it is)
  registerHoverProvider(monaco, getSchema);

  languageRegistered = true;
}

/**
 * Initialize editors for the current page.
 * Called on initial load and after each instant navigation.
 */
async function initPage(): Promise<void> {
  // Prevent concurrent execution (e.g. document$ ReplaySubject firing
  // while the initial initPage() is still loading Monaco from CDN).
  if (initInProgress) return;
  initInProgress = true;

  try {
    // Dispose previous editors (from prior page)
    if (currentManager) {
      currentManager.dispose();
      currentManager = null;
    }

    // Skip Monaco on narrow viewports — touch devices lack hover and the
    // editors need horizontal space.  Pygments static highlighting remains.
    if (window.innerWidth < 768) return;

    // Check if there are IDF code blocks on this page.
    // Zensical/pymdownx puts the language class on a wrapper <div>, not on <code>.
    // Structure: <div class="language-idf highlight"><pre><code>...</code></pre></div>
    const codeBlocks = document.querySelectorAll('div.language-idf pre > code');
    if (codeBlocks.length === 0) return;

    // Load Monaco from CDN (cached after first load)
    const monaco = await loadMonacoFromCDN();

    // Register language and providers (once)
    registerLanguage(monaco);

    // Start loading IDD schema in the background (for hover docs)
    loadSchema();

    // Create editor manager and initialize editors
    currentManager = new EditorManager(monaco);
    currentManager.initialize(codeBlocks);
  } catch (error) {
    console.error('[idf-editor] Failed to initialize:', error);
  } finally {
    initInProgress = false;
  }
}

/**
 * Hook into Zensical's instant navigation system.
 * The document$ observable emits on each page navigation.
 */
function hookInstantNav(): boolean {
  const win = window as Record<string, unknown>;
  const document$ = win.document$ as { subscribe: (fn: () => void) => void } | undefined;

  if (!document$) return false;

  // document$ is a ReplaySubject — it replays the last value on subscribe.
  // Skip that initial emission since initPage() already handles the first load.
  let firstEmission = true;

  document$.subscribe(() => {
    if (firstEmission) {
      firstEmission = false;
      return;
    }

    // Small delay to ensure the DOM is updated
    requestAnimationFrame(() => initPage());
  });

  return true;
}

// --- Bootstrap ---

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initPage());
} else {
  initPage();
}

// Hook into instant navigation (may not be available immediately)
if (!hookInstantNav()) {
  let attempts = 0;
  const interval = setInterval(() => {
    attempts++;
    if (hookInstantNav() || attempts > 50) {
      clearInterval(interval);
    }
  }, 100);
}
