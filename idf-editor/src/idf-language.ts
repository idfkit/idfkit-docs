/**
 * IDF language registration for Monaco.
 *
 * The editor owns no grammar. Token boundaries come from `scanIdf` and
 * `classify` in `@idfkit/core`, the same syntax layer the parser, Envelop and
 * idfkit-lsp use, and are handed to Monaco through a document semantic tokens
 * provider. What remains here is the mapping from token kind to theme scope.
 */

import { classify, scanIdf, type Token, type TokenKind } from '@idfkit/core';
import type * as Monaco from 'monaco-editor';

/** Language ID for IDF files */
export const IDF_LANGUAGE_ID = 'idf';

/** IDF language configuration (comment toggling and word boundaries). */
export const idfLanguageConfiguration: Monaco.languages.LanguageConfiguration = {
  comments: {
    lineComment: '!',
  },
  brackets: [],
  autoClosingPairs: [],
  surroundingPairs: [],
  wordPattern: /[A-Za-z][A-Za-z0-9:_-]*/,
};

/**
 * Theme scope for each token kind, or `null` for a kind that is not drawn.
 *
 * Written as a record so that it is total over `TokenKind`: a kind added
 * upstream without an entry here is a type error rather than an uncoloured span.
 * Two kinds are split once more in `scopeFor`, `value` into `number` and
 * `string` and `comment` into field labels and other comments; both are
 * presentation choices over spans the package already delimited.
 */
const TOKEN_SCOPE: Readonly<Record<TokenKind, string | null>> = {
  comment: 'comment',
  typeName: 'type',
  value: 'string',
  separator: 'delimiter',
  terminator: 'delimiter.semicolon',
  trivia: null,
};

/** Scope for values that read as numbers. */
const NUMBER_SCOPE = 'number';

/** Scope for `!-` comments, the convention by which IDF files label each field. */
const FIELD_LABEL_SCOPE = 'comment.doc';

/** Token types registered with Monaco, in legend order. */
const TOKEN_TYPES: readonly string[] = [
  ...new Set([
    ...Object.values(TOKEN_SCOPE).filter((scope): scope is string => scope !== null),
    NUMBER_SCOPE,
    FIELD_LABEL_SCOPE,
  ]),
];

const SCOPE_INDEX: ReadonlyMap<string, number> = new Map(TOKEN_TYPES.map((scope, index) => [scope, index]));

const NUMERIC_VALUE = /^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/;

/** Scope for one classified token of `text`, or `null` when it is not drawn. */
function scopeFor(token: Token, text: string): string | null {
  if (token.kind === 'value' && NUMERIC_VALUE.test(text.slice(token.start, token.end).trim())) return NUMBER_SCOPE;
  if (token.kind === 'comment' && text.startsWith('!-', token.start)) return FIELD_LABEL_SCOPE;
  return TOKEN_SCOPE[token.kind];
}

/**
 * Encode a model's tokens in Monaco's five-integer delta form.
 *
 * `classify` splits tokens at line boundaries, but in @idfkit/core 0.4.0 the
 * piece before a break keeps the line terminator: a value in an unterminated
 * statement (an output-variable listing, say) ends with `\n`. Monaco expects
 * every token to end within its line and logs an error for each one that does
 * not, so each length is clamped to the remainder of its line.
 */
function encodeTokens(model: Monaco.editor.ITextModel): Uint32Array {
  const text = model.getValue();
  const data: number[] = [];
  let lastLine = 0;
  let lastColumn = 0;

  for (const token of classify(scanIdf(text))) {
    const scope = scopeFor(token, text);
    if (scope === null) continue;

    const position = model.getPositionAt(token.start);
    const line = position.lineNumber - 1;
    const column = position.column - 1;
    const length = Math.min(token.end - token.start, model.getLineLength(position.lineNumber) - column);
    if (length <= 0) continue;

    data.push(
      line - lastLine,
      line === lastLine ? column - lastColumn : column,
      length,
      SCOPE_INDEX.get(scope) ?? 0,
      0
    );
    lastLine = line;
    lastColumn = column;
  }

  return new Uint32Array(data);
}

/**
 * Register the IDF language, its configuration and its semantic tokens provider.
 *
 * Code blocks in the documentation are short and read-only, so tokens are
 * computed synchronously on request rather than in a worker.
 */
export function registerIdfLanguage(monaco: typeof Monaco): void {
  monaco.languages.register({
    id: IDF_LANGUAGE_ID,
    extensions: ['.idf', '.imf'],
    aliases: ['IDF', 'EnergyPlus IDF', 'Input Data File'],
    mimetypes: ['text/x-idf'],
  });
  monaco.languages.setLanguageConfiguration(IDF_LANGUAGE_ID, idfLanguageConfiguration);

  monaco.languages.registerDocumentSemanticTokensProvider(IDF_LANGUAGE_ID, {
    getLegend: () => ({ tokenTypes: [...TOKEN_TYPES], tokenModifiers: [] }),
    provideDocumentSemanticTokens: (model) => ({ data: encodeTokens(model) }),
    releaseDocumentSemanticTokens: () => undefined,
  });
}
