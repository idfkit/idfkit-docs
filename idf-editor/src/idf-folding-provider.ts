/**
 * IDF Folding Provider
 *
 * Provides code folding for IDF code blocks, allowing users to collapse
 * and expand individual IDF objects (from class name to semicolon).
 */

import type * as Monaco from 'monaco-editor';
import { IDF_LANGUAGE_ID } from './idf-language';

/**
 * Register a folding range provider for IDF files.
 *
 * Folds IDF objects from the class name line (ending with comma)
 * to the last field line (ending with semicolon).
 */
export function registerFoldingProvider(monaco: typeof Monaco): Monaco.IDisposable {
  return monaco.languages.registerFoldingRangeProvider(IDF_LANGUAGE_ID, {
    provideFoldingRanges(model): Monaco.languages.FoldingRange[] {
      const ranges: Monaco.languages.FoldingRange[] = [];
      const lineCount = model.getLineCount();
      let objectStart: number | null = null;

      for (let i = 1; i <= lineCount; i++) {
        const line = model.getLineContent(i);
        // Strip comments to get the code content
        const trimmed = line.replace(/!.*$/, '').trim();

        // Detect class name line: word followed by comma at start of line
        if (/^[A-Za-z][A-Za-z0-9:_-]*\s*,/.test(trimmed)) {
          // Close previous object if still open
          if (objectStart !== null && i > objectStart + 1) {
            ranges.push({
              start: objectStart,
              end: i - 1,
              kind: monaco.languages.FoldingRangeKind.Region,
            });
          }
          objectStart = i;
        }

        // Detect end of object (semicolon)
        if (trimmed.endsWith(';') && objectStart !== null) {
          if (i > objectStart) {
            ranges.push({
              start: objectStart,
              end: i,
              kind: monaco.languages.FoldingRangeKind.Region,
            });
          }
          objectStart = null;
        }
      }

      return ranges;
    },
  });
}
