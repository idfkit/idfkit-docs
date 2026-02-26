/**
 * IDF Hover Documentation Service
 *
 * Provides hover tooltips for IDF code blocks, showing IDD schema documentation
 * when the user hovers over object class names or field values.
 *
 * Extracted from the Envelop project (src/editor/idf-language-service.ts),
 * keeping only the hover-related functionality.
 */

import type * as Monaco from 'monaco-editor';
import { IDF_LANGUAGE_ID } from './idf-language';
import type { CompactIDDSchema, CompactIDDObjectType, CompactIDDField } from './types';

/**
 * Register hover provider for IDF files.
 *
 * @param monaco - The Monaco editor instance
 * @param getSchema - Function that returns the current IDD schema (or null if not loaded)
 * @returns A disposable to unregister the provider
 */
export function registerHoverProvider(
  monaco: typeof Monaco,
  getSchema: () => CompactIDDSchema | null
): Monaco.IDisposable {
  return monaco.languages.registerHoverProvider(IDF_LANGUAGE_ID, {
    provideHover(model, position): Monaco.languages.Hover | null {
      const schema = getSchema();
      if (!schema) {
        return null;
      }

      const context = getHoverContext(model, position);
      if (!context) {
        return null;
      }

      const objectType = schema.objectTypes[context.className.toLowerCase()];
      if (!objectType) {
        return null;
      }

      // Hovering over class name
      if (context.isClassName) {
        return createObjectHover(objectType, position);
      }

      // Hovering over a field value
      if (context.fieldIndex !== undefined && context.fieldIndex < objectType.fields.length) {
        const field = objectType.fields[context.fieldIndex];
        if (field) {
          return createFieldHover(field, objectType);
        }
      }

      return null;
    },
  });
}

/** Hover context describing what the cursor is over */
interface HoverContext {
  className: string;
  isClassName: boolean;
  fieldIndex?: number;
}

/** Get context for hover documentation at the given position */
function getHoverContext(
  model: Monaco.editor.ITextModel,
  position: Monaco.Position
): HoverContext | null {
  const lineContent = model.getLineContent(position.lineNumber);

  // Check if we're hovering over a class name
  const classMatch = lineContent.match(/^([A-Za-z][A-Za-z0-9:_-]*)\s*,/);
  if (classMatch && classMatch[1]) {
    const classNameEnd = classMatch[1].length;
    if (position.column <= classNameEnd + 1) {
      return { className: classMatch[1], isClassName: true };
    }
  }

  // Find the current object
  const objectContext = findCurrentObject(model, position);
  if (objectContext) {
    const fieldIndex = countFieldsSoFar(model, objectContext.startLine, position);
    return {
      className: objectContext.className,
      isClassName: false,
      fieldIndex,
    };
  }

  return null;
}

/** Find the current object context (class name and start line) */
function findCurrentObject(
  model: Monaco.editor.ITextModel,
  position: Monaco.Position
): { className: string; startLine: number } | null {
  for (let line = position.lineNumber; line >= 1; line--) {
    const lineContent = model.getLineContent(line);

    // Look for class name pattern: "ClassName,"
    const match = lineContent.match(/^([A-Za-z][A-Za-z0-9:_-]*)\s*,/);
    if (match && match[1]) {
      return { className: match[1], startLine: line };
    }

    // If we hit a semicolon, we've gone past our object
    if (lineContent.includes(';') && line < position.lineNumber) {
      break;
    }
  }

  return null;
}

/** Count the number of fields (commas) from object start to current position */
function countFieldsSoFar(
  model: Monaco.editor.ITextModel,
  startLine: number,
  position: Monaco.Position
): number {
  let fieldCount = 0;

  for (let line = startLine; line <= position.lineNumber; line++) {
    const lineContent = model.getLineContent(line);
    const endCol = line === position.lineNumber ? position.column - 1 : lineContent.length;
    const text = lineContent.substring(0, endCol);

    // Remove comments
    const withoutComments = text.replace(/!.*$/, '');

    // Count commas
    const commas = (withoutComments.match(/,/g) || []).length;
    fieldCount += commas;

    // The first comma after class name is field 0's delimiter
    if (line === startLine && commas > 0) {
      fieldCount--;
    }
  }

  return fieldCount;
}

/** Create hover content for an object type */
function createObjectHover(
  objectType: CompactIDDObjectType,
  position: Monaco.Position
): Monaco.languages.Hover {
  const contents: Monaco.IMarkdownString[] = [];

  // Title
  contents.push({ value: `**${objectType.name}**` });

  // Group
  if (objectType.group) {
    contents.push({ value: `*Group: ${objectType.group}*` });
  }

  // Memo
  if (objectType.memo) {
    contents.push({ value: objectType.memo });
  }

  // Properties
  const props: string[] = [];
  if (objectType.isUnique) props.push('unique-object');
  if (objectType.isRequired) props.push('required-object');
  if (objectType.minFields > 0) props.push(`min-fields: ${String(objectType.minFields)}`);
  if (objectType.extensible > 0) props.push(`extensible: ${String(objectType.extensible)}`);

  if (props.length > 0) {
    contents.push({ value: `\`${props.join(' | ')}\`` });
  }

  return {
    contents,
    range: {
      startLineNumber: position.lineNumber,
      startColumn: 1,
      endLineNumber: position.lineNumber,
      endColumn: objectType.name.length + 1,
    },
  };
}

/** Create hover content for a field */
function createFieldHover(
  field: CompactIDDField,
  objectType: CompactIDDObjectType
): Monaco.languages.Hover {
  const contents: Monaco.IMarkdownString[] = [];

  // Title
  contents.push({ value: `**${field.name || field.id}** (${objectType.name})` });

  // Type and units
  let typeInfo = `Type: \`${field.type}\``;
  if (field.units) {
    typeInfo += ` | Units: \`${field.units}\``;
  }
  contents.push({ value: typeInfo });

  // Memo
  if (field.memo) {
    contents.push({ value: field.memo });
  }

  // Range constraints
  if (field.minimum !== undefined || field.maximum !== undefined) {
    let range = 'Range: ';
    if (field.minimum !== undefined) {
      range += field.exclusiveMinimum ? `> ${String(field.minimum)}` : `>= ${String(field.minimum)}`;
    }
    if (field.minimum !== undefined && field.maximum !== undefined) {
      range += ' and ';
    }
    if (field.maximum !== undefined) {
      range += field.exclusiveMaximum ? `< ${String(field.maximum)}` : `<= ${String(field.maximum)}`;
    }
    contents.push({ value: range });
  }

  // Default value
  if (field.default) {
    contents.push({ value: `Default: \`${field.default}\`` });
  }

  // Choices
  if (field.choices && field.choices.length > 0) {
    contents.push({ value: `Choices: ${field.choices.map((c) => `\`${c}\``).join(', ')}` });
  }

  // Properties
  const props: string[] = [];
  if (field.required) props.push('required');
  if (field.autosizable) props.push('autosizable');
  if (field.autocalculatable) props.push('autocalculatable');

  if (props.length > 0) {
    contents.push({ value: `\`${props.join(' | ')}\`` });
  }

  return { contents };
}
