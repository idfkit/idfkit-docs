/**
 * Compact IDD Schema Types for Browser
 *
 * These are simplified versions of the Envelop project's IDD types,
 * optimized for the hover documentation use case. They use plain
 * objects/Records instead of Maps for JSON serialization.
 */

/** Field type enumeration */
export type IDDFieldType =
  | 'real'
  | 'integer'
  | 'alpha'
  | 'choice'
  | 'object-list'
  | 'external-list'
  | 'node';

/** Compact field definition for hover docs */
export interface CompactIDDField {
  /** Field identifier (A1, A2, N1, N2, etc.) */
  id: string;
  /** Field name from \field tag */
  name: string;
  /** Data type */
  type: IDDFieldType;
  /** Whether this field is required */
  required: boolean;
  /** Default value */
  default?: string;
  /** Unit specification (e.g., "m", "W", "degC") */
  units?: string;
  /** Minimum value */
  minimum?: number;
  /** Whether minimum is exclusive */
  exclusiveMinimum?: boolean;
  /** Maximum value */
  maximum?: number;
  /** Whether maximum is exclusive */
  exclusiveMaximum?: boolean;
  /** Valid choices for 'choice' type fields */
  choices?: string[];
  /** Documentation text */
  memo: string;
  /** Whether this field can be autosized */
  autosizable: boolean;
  /** Whether this field can be autocalculated */
  autocalculatable: boolean;
}

/** Compact object type definition for hover docs */
export interface CompactIDDObjectType {
  /** Object class name (e.g., "Building", "Zone") */
  name: string;
  /** Group this object belongs to */
  group: string;
  /** Documentation from \memo tags */
  memo: string;
  /** Field definitions */
  fields: CompactIDDField[];
  /** Minimum number of fields required */
  minFields: number;
  /** Only one instance allowed */
  isUnique: boolean;
  /** Must exist in every model */
  isRequired: boolean;
  /** Number of fields in extensible group */
  extensible: number;
}

/** The complete compact IDD schema */
export interface CompactIDDSchema {
  /** EnergyPlus version */
  version: string;
  /** Object types keyed by lowercase name */
  objectTypes: Record<string, CompactIDDObjectType>;
}
