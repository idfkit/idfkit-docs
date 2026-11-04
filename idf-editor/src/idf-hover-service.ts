/**
 * IDF hover documentation.
 *
 * What the cursor is on, and what the schema says about it, is answered by
 * `explainAt` from `@idfkit/language`. This module only translates that answer
 * into Monaco's hover shape: every fact shown is the package's, and the
 * labels and their order are the only things decided here.
 */

import { describeObjectType, type FieldDescription, type Schema } from '@idfkit/core';
import { explainAt, type Explanation } from '@idfkit/language';
import type * as Monaco from 'monaco-editor';
import { IDF_LANGUAGE_ID } from './idf-language';
import { currentProse, currentSchema } from './schema-source';

/** Choices are listed inline up to this count, and as a bulleted list beyond it. */
const INLINE_CHOICES = 5;

/** Register the hover provider for IDF code blocks. */
export function registerHoverProvider(monaco: typeof Monaco): Monaco.IDisposable {
  return monaco.languages.registerHoverProvider(IDF_LANGUAGE_ID, {
    provideHover(model, position): Monaco.languages.Hover | null {
      const schema = currentSchema();
      if (schema === undefined) return null;

      const result = explainAt(model.getValue(), model.getOffsetAt(position), schema, currentProse());
      if (result.status !== 'ok') return null;

      const { explanation } = result;
      const start = model.getPositionAt(explanation.region.start);
      const end = model.getPositionAt(explanation.region.end);

      return {
        contents: hoverLines(explanation, schema).map((value) => ({ value })),
        range: new monaco.Range(start.lineNumber, start.column, end.lineNumber, end.column),
      };
    },
  });
}

/**
 * Text escaped so that Markdown renders it literally.
 *
 * The schema's names and prose are plain text, but Monaco renders a hover as
 * Markdown: unescaped, the placeholder in "a default Space named <Zone Name>"
 * is removed as an HTML tag, and the asterisks in "Curve:* or Table:Lookup"
 * become emphasis. CommonMark accepts a backslash before any ASCII punctuation
 * character, so every character with a Markdown meaning is escaped.
 */
function literal(text: string): string {
  return text.replace(/[\\`*_{}[\]()<>#+\-.!|~&]/g, '\\$&');
}

/** The Markdown paragraphs a hover shows, in order. */
function hoverLines(explanation: Explanation, schema: Schema): string[] {
  const lines = explanation.of === 'objectType' ? objectLines(explanation, schema) : fieldLines(explanation);

  if (explanation.docs !== undefined) {
    lines.push(`[${literal(explanation.docs.label)}](${explanation.docs.url})`);
  }
  return lines;
}

function objectLines(explanation: Explanation, schema: Schema): string[] {
  const lines = [`**${literal(explanation.typeName)}**`];
  if (explanation.prose !== undefined) lines.push(literal(explanation.prose));

  const description = describeObjectType(schema, explanation.typeName);
  const props: string[] = [];
  if (description.requiredFields.length > 0) props.push(`required fields: ${String(description.requiredFields.length)}`);
  if (description.isExtensible && description.extensibleSize !== undefined) {
    props.push(`extensible: ${String(description.extensibleSize)}`);
  }
  if (props.length > 0) lines.push(`\`${props.join(' | ')}\``);
  return lines;
}

function fieldLines(explanation: Explanation): string[] {
  const { field } = explanation;
  const lines = [`**${literal(explanation.fieldName ?? '')}** (${literal(explanation.typeName)})`];

  if (field !== undefined) {
    let typeInfo = field.fieldType !== undefined ? `Type: \`${field.fieldType}\`` : '';
    if (field.units !== undefined) typeInfo += `${typeInfo ? ' | ' : ''}Units: \`${field.units}\``;
    if (typeInfo) lines.push(typeInfo);
  }

  if (explanation.prose !== undefined) lines.push(literal(explanation.prose));
  if (field === undefined) return lines;

  const range = rangeText(field);
  if (range !== undefined) lines.push(`Range: ${range}`);

  if (field.default !== undefined) lines.push(`Default: \`${String(field.default)}\``);

  // The schema lists an empty string among the choices of fields that may be left blank; a blank
  // is not something a reader chooses, so it is not shown.
  const choices = (field.enumValues ?? [])
    .map((choice) => String(choice))
    .filter((choice) => choice !== '')
    .map((choice) => `\`${choice}\``);
  if (choices.length > 0) {
    lines.push(
      choices.length <= INLINE_CHOICES
        ? `Choices: ${choices.join(', ')}`
        : `Choices (${String(choices.length)}):\n${choices.map((choice) => `- ${choice}`).join('\n')}`
    );
  }

  if (field.isReference && field.objectList !== undefined && field.objectList.length > 0) {
    lines.push(`References: ${field.objectList.map((name) => `\`${name}\``).join(', ')}`);
  }

  if (field.required) lines.push('`required`');
  return lines;
}

/**
 * The field's numeric bounds as text, or `undefined` when it has none.
 *
 * The schema states an exclusive bound either as a flag beside `minimum` or as
 * the bound itself, and both forms are read here.
 */
function rangeText(field: FieldDescription): string | undefined {
  const parts: string[] = [];

  if (typeof field.exclusiveMinimum === 'number') parts.push(`> ${String(field.exclusiveMinimum)}`);
  else if (field.minimum !== undefined) {
    parts.push(`${field.exclusiveMinimum === true ? '>' : '>='} ${String(field.minimum)}`);
  }

  if (typeof field.exclusiveMaximum === 'number') parts.push(`< ${String(field.exclusiveMaximum)}`);
  else if (field.maximum !== undefined) {
    parts.push(`${field.exclusiveMaximum === true ? '<' : '<='} ${String(field.maximum)}`);
  }

  return parts.length > 0 ? parts.join(' and ') : undefined;
}
