/**
 * Editor Manager
 *
 * Manages the lifecycle of Monaco editor instances embedded in documentation
 * pages. Handles:
 * - Discovering IDF code blocks on the page
 * - Lazy-loading editors via IntersectionObserver
 * - Creating read-only Monaco editor instances
 * - Theme synchronization with Zensical's dark/light toggle
 * - Cleanup on page navigation (instant nav)
 * - Copy-to-clipboard button
 */

import type * as Monaco from 'monaco-editor';
import { getCurrentTheme, THEME_DARK, THEME_LIGHT } from './idf-themes';

/** Minimum editor height in pixels (3 lines) */
const MIN_HEIGHT = 60;
/** Maximum editor height before scrolling (40 lines) */
const MAX_HEIGHT = 720;
/** Line height for height calculation (matches fontSize 13) */
const LINE_HEIGHT = 19;
/** Padding (top + bottom, matches Monaco padding option) */
const PADDING = 20;
/** IntersectionObserver rootMargin for pre-loading */
const PRELOAD_MARGIN = '200px';
/** Minimum viewport width to enable Monaco (skip on mobile/narrow screens) */
const MIN_VIEWPORT_WIDTH = 768;

/** Monaco editor version to load from CDN */
const MONACO_VERSION = '0.55.1';
const MONACO_CDN_BASE = `https://cdn.jsdelivr.net/npm/monaco-editor@${MONACO_VERSION}/min/vs`;

/** Copy icon SVG */
const COPY_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`;
const CHECK_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`;

/** Tracked editor instance */
interface EditorInstance {
  editor: Monaco.editor.IStandaloneCodeEditor;
  container: HTMLElement;
}

export class EditorManager {
  private monaco: typeof Monaco;
  private editors: EditorInstance[] = [];
  private observer: IntersectionObserver | null = null;
  private themeObserver: MutationObserver | null = null;
  private pendingBlocks: Map<Element, { wrapper: HTMLElement; code: string }> = new Map();

  constructor(monaco: typeof Monaco) {
    this.monaco = monaco;
  }

  /**
   * Initialize the editor manager for the current page.
   * Finds all IDF code blocks and sets up lazy loading.
   */
  initialize(codeBlocks: NodeListOf<Element>): void {
    if (codeBlocks.length === 0) return;

    // Set up IntersectionObserver for lazy loading
    this.observer = new IntersectionObserver(
      (entries) => this.handleIntersection(entries),
      { rootMargin: PRELOAD_MARGIN }
    );

    // Process each code block.
    // Structure: <div class="language-idf highlight"><pre>...<code>...</code></pre></div>
    codeBlocks.forEach((codeEl) => {
      const pre = codeEl.parentElement;
      if (!pre || pre.tagName !== 'PRE') return;

      // The wrapper div has the language-idf class
      const wrapper = pre.parentElement;
      if (!wrapper) return;

      // Skip if already converted
      if (wrapper.dataset.idfEditor === 'true') return;

      const code = codeEl.textContent || '';
      this.pendingBlocks.set(wrapper, { wrapper: wrapper as HTMLElement, code });
      this.observer!.observe(wrapper);
    });

    // Set up theme change listener
    this.watchThemeChanges();
  }

  /**
   * Check whether any tracked element (editor container or pending block)
   * is still attached to the live document.  Returns false when Zensical's
   * instant navigation has replaced the page content.
   */
  isStillInDOM(): boolean {
    for (const { container } of this.editors) {
      if (document.contains(container)) return true;
    }
    for (const [element] of this.pendingBlocks) {
      if (document.contains(element)) return true;
    }
    return false;
  }

  /** Dispose all editors and observers */
  dispose(): void {
    // Dispose editors
    for (const { editor } of this.editors) {
      editor.dispose();
    }
    this.editors = [];

    // Disconnect observers
    this.observer?.disconnect();
    this.observer = null;
    this.themeObserver?.disconnect();
    this.themeObserver = null;

    // Clear pending blocks
    this.pendingBlocks.clear();
  }

  /** Handle IntersectionObserver callbacks */
  private handleIntersection(entries: IntersectionObserverEntry[]): void {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;

      const block = this.pendingBlocks.get(entry.target);
      if (!block) continue;

      // Stop observing this element
      this.observer?.unobserve(entry.target);
      this.pendingBlocks.delete(entry.target);

      // Create the editor
      this.createEditor(block.wrapper, block.code);
    }
  }

  /** Create a Monaco editor replacing the given wrapper element */
  private createEditor(wrapper: HTMLElement, code: string): void {
    // Calculate height based on line count
    const lineCount = code.split('\n').length;
    const height = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, lineCount * LINE_HEIGHT + PADDING));

    // Create container
    const container = document.createElement('div');
    container.className = 'idf-editor-container';
    container.style.height = `${height}px`;

    // Replace the wrapper <div> element
    wrapper.parentNode?.replaceChild(container, wrapper);
    wrapper.dataset.idfEditor = 'true';

    // Create the editor
    const editor = this.monaco.editor.create(container, {
      value: code,
      language: 'idf',
      theme: getCurrentTheme(),
      readOnly: true,
      domReadOnly: true,
      minimap: { enabled: false },
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      wordWrap: 'off',
      folding: false,
      glyphMargin: false,
      lineDecorationsWidth: 8,
      lineNumbersMinChars: 3,
      renderLineHighlight: 'none',
      overviewRulerLanes: 0,
      hideCursorInOverviewRuler: true,
      overviewRulerBorder: false,
      scrollbar: {
        vertical: 'auto',
        horizontal: 'auto',
        verticalScrollbarSize: 8,
        horizontalScrollbarSize: 8,
      },
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, monospace",
      padding: { top: 8, bottom: 8 },
      automaticLayout: true,
      contextmenu: false,
      links: false,
      renderValidationDecorations: 'off',
      // Render hover/suggestion widgets outside the editor so they aren't clipped
      fixedOverflowWidgets: true,
      // Accessibility for read-only blocks
      accessibilitySupport: 'off',
      ariaLabel: 'EnergyPlus IDF code example',
    });

    // Add copy button
    this.addCopyButton(container, editor);

    // Track the editor
    this.editors.push({ editor, container });
  }

  /** Add a copy-to-clipboard button to the editor container */
  private addCopyButton(container: HTMLElement, editor: Monaco.editor.IStandaloneCodeEditor): void {
    const btn = document.createElement('button');
    btn.className = 'idf-editor-copy';
    btn.title = 'Copy to clipboard';
    btn.innerHTML = COPY_ICON;

    btn.addEventListener('click', async () => {
      try {
        const text = editor.getValue();
        await navigator.clipboard.writeText(text);
        btn.innerHTML = CHECK_ICON;
        btn.classList.add('copied');
        setTimeout(() => {
          btn.innerHTML = COPY_ICON;
          btn.classList.remove('copied');
        }, 2000);
      } catch {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = editor.getValue();
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        btn.innerHTML = CHECK_ICON;
        btn.classList.add('copied');
        setTimeout(() => {
          btn.innerHTML = COPY_ICON;
          btn.classList.remove('copied');
        }, 2000);
      }
    });

    container.appendChild(btn);
  }

  /** Watch for Zensical theme changes and update all editors */
  private watchThemeChanges(): void {
    this.themeObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.attributeName === 'data-md-color-scheme') {
          const scheme = document.body.getAttribute('data-md-color-scheme');
          const theme = scheme === 'slate' ? THEME_DARK : THEME_LIGHT;
          this.monaco.editor.setTheme(theme);
        }
      }
    });

    this.themeObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ['data-md-color-scheme'],
    });
  }
}

/** Cached promise for Monaco loading (prevents duplicate loader injection) */
let monacoLoadPromise: Promise<typeof Monaco> | null = null;

/**
 * Load Monaco editor from CDN using the AMD loader.
 *
 * Returns the Monaco editor module. The loader and editor core are
 * cached by the browser across page navigations. The promise is
 * cached so concurrent calls share the same load operation.
 */
export function loadMonacoFromCDN(): Promise<typeof Monaco> {
  if (monacoLoadPromise) return monacoLoadPromise;

  monacoLoadPromise = new Promise((resolve, reject) => {
    // Check if Monaco is already loaded
    const win = window as Record<string, unknown>;
    if (win.monaco) {
      resolve(win.monaco as typeof Monaco);
      return;
    }

    // Check if the AMD loader is already present
    if (typeof (win.require as Function) === 'function' && (win.require as Record<string, unknown>).config) {
      configureAndLoadMonaco(resolve, reject);
      return;
    }

    // Inject the AMD loader script
    const script = document.createElement('script');
    script.src = `${MONACO_CDN_BASE}/loader.js`;
    script.onload = () => configureAndLoadMonaco(resolve, reject);
    script.onerror = () => reject(new Error('Failed to load Monaco AMD loader'));
    document.head.appendChild(script);
  });

  return monacoLoadPromise;
}

function configureAndLoadMonaco(
  resolve: (monaco: typeof Monaco) => void,
  reject: (error: Error) => void
): void {
  const win = window as Record<string, unknown>;
  const require = win.require as {
    config: (opts: Record<string, unknown>) => void;
    (deps: string[], callback: (monaco: typeof Monaco) => void, errorback?: (err: Error) => void): void;
  };

  require.config({ paths: { vs: MONACO_CDN_BASE } });
  require(
    ['vs/editor/editor.main'],
    (monaco: typeof Monaco) => {
      resolve(monaco);
    },
    (err: Error) => {
      reject(err);
    }
  );
}
