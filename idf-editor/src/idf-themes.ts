/**
 * Monaco Editor Themes for IDF Documentation
 *
 * Light and dark themes adapted from the Envelop project, with colors
 * tuned to match Zensical's Material Design palette (teal/amber with
 * default and slate color schemes).
 */

/** IDF theme token rules for dark mode */
const idfDarkThemeRules: { token: string; foreground?: string; fontStyle?: string }[] = [
  { token: 'comment', foreground: '6A9955' },
  { token: 'comment.doc', foreground: '6A9955', fontStyle: 'italic' },
  { token: 'type', foreground: '4EC9B0' },
  { token: 'type.identifier', foreground: '4EC9B0', fontStyle: 'bold' },
  { token: 'keyword', foreground: '569CD6' },
  { token: 'number', foreground: 'B5CEA8' },
  { token: 'number.float', foreground: 'B5CEA8' },
  { token: 'string', foreground: 'CE9178' },
  { token: 'string.date', foreground: 'DCDCAA' },
  { token: 'delimiter', foreground: 'D4D4D4' },
  { token: 'delimiter.semicolon', foreground: 'D4D4D4', fontStyle: 'bold' },
  { token: 'constant', foreground: '4FC1FF' },
];

/** IDF theme token rules for light mode */
const idfLightThemeRules: { token: string; foreground?: string; fontStyle?: string }[] = [
  { token: 'comment', foreground: '008000' },
  { token: 'comment.doc', foreground: '008000', fontStyle: 'italic' },
  { token: 'type', foreground: '267F99' },
  { token: 'type.identifier', foreground: '267F99', fontStyle: 'bold' },
  { token: 'keyword', foreground: '0000FF' },
  { token: 'number', foreground: '098658' },
  { token: 'number.float', foreground: '098658' },
  { token: 'string', foreground: 'A31515' },
  { token: 'string.date', foreground: '795E26' },
  { token: 'delimiter', foreground: '000000' },
  { token: 'delimiter.semicolon', foreground: '000000', fontStyle: 'bold' },
  { token: 'constant', foreground: '0070C1' },
];

/** Theme name constants */
export const THEME_LIGHT = 'idf-docs-light';
export const THEME_DARK = 'idf-docs-dark';

/**
 * Register both light and dark themes with Monaco.
 *
 * Background and widget colors are tuned to match Zensical's Material Design
 * theme: "default" scheme for light, "slate" scheme for dark.
 */
export function registerIDFThemes(monaco: { editor: { defineTheme: Function } }): void {
  monaco.editor.defineTheme(THEME_DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: idfDarkThemeRules,
    colors: {
      'editor.background': '#212121', // Matches Zensical slate code bg
      'editor.foreground': '#e2e8f0',
      'editor.lineHighlightBackground': '#2d2d2d',
      'editor.selectionBackground': '#264f78',
      'editorLineNumber.foreground': '#6b7280',
      'editorCursor.foreground': '#e2e8f0',
      'editorWidget.background': '#2d2d2d',
      'editorWidget.border': '#404040',
      'editorHoverWidget.background': '#2d2d2d',
      'editorHoverWidget.border': '#404040',
    },
  });

  monaco.editor.defineTheme(THEME_LIGHT, {
    base: 'vs',
    inherit: true,
    rules: idfLightThemeRules,
    colors: {
      'editor.background': '#f5f5f5', // Matches Zensical default code bg
      'editor.foreground': '#1a202c',
      'editor.lineHighlightBackground': '#f0f0f0',
      'editor.selectionBackground': '#c8e1ff',
      'editorLineNumber.foreground': '#a0aec0',
      'editorCursor.foreground': '#1a202c',
      'editorWidget.background': '#ffffff',
      'editorWidget.border': '#e2e8f0',
      'editorHoverWidget.background': '#ffffff',
      'editorHoverWidget.border': '#e2e8f0',
    },
  });
}

/** Get the appropriate theme name based on Zensical's color scheme */
export function getCurrentTheme(): string {
  const scheme = document.body.getAttribute('data-md-color-scheme');
  return scheme === 'slate' ? THEME_DARK : THEME_LIGHT;
}
