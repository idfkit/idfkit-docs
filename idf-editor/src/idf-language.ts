/**
 * IDF Language Definition for Monaco Editor
 *
 * Provides syntax highlighting, tokenization, and language configuration
 * for EnergyPlus IDF (Input Data File) format.
 *
 * Adapted from the Envelop project (src/editor/idf-language.ts).
 */

import type { languages } from 'monaco-editor';

/** Language ID for IDF files */
export const IDF_LANGUAGE_ID = 'idf';

/** IDF Language configuration */
export const idfLanguageConfiguration: languages.LanguageConfiguration = {
  comments: {
    lineComment: '!',
  },
  brackets: [],
  autoClosingPairs: [],
  surroundingPairs: [],
  folding: {
    markers: {
      start: /^!-\s*={3,}\s*ALL OBJECTS IN CLASS:/i,
      end: /^!-\s*={3,}\s*ALL OBJECTS IN CLASS:/i,
    },
  },
  wordPattern: /[A-Za-z][A-Za-z0-9:_-]*/,
};

/** Common EnergyPlus object class names for highlighting */
const COMMON_CLASSES = [
  'Version',
  'SimulationControl',
  'Building',
  'Timestep',
  'RunPeriod',
  'Site:Location',
  'SizingPeriod:DesignDay',
  'GlobalGeometryRules',
  'Zone',
  'ZoneList',
  'BuildingSurface:Detailed',
  'FenestrationSurface:Detailed',
  'Wall:Exterior',
  'Wall:Interior',
  'Roof',
  'Floor:GroundContact',
  'Window',
  'Door',
  'Material',
  'Material:NoMass',
  'Material:AirGap',
  'WindowMaterial:SimpleGlazingSystem',
  'WindowMaterial:Glazing',
  'Construction',
  'Schedule:Compact',
  'Schedule:Constant',
  'Schedule:Day:Interval',
  'Schedule:Week:Daily',
  'Schedule:Year',
  'ScheduleTypeLimits',
  'People',
  'Lights',
  'ElectricEquipment',
  'ZoneInfiltration:DesignFlowRate',
  'ZoneVentilation:DesignFlowRate',
  'Sizing:Zone',
  'Sizing:System',
  'Sizing:Plant',
  'ZoneHVAC:IdealLoadsAirSystem',
  'ZoneHVAC:EquipmentList',
  'ZoneHVAC:EquipmentConnections',
  'ThermostatSetpoint:SingleHeating',
  'ThermostatSetpoint:SingleCooling',
  'ThermostatSetpoint:DualSetpoint',
  'ZoneControl:Thermostat',
  'AirLoopHVAC',
  'AirLoopHVAC:ZoneSplitter',
  'AirLoopHVAC:ZoneMixer',
  'Fan:ConstantVolume',
  'Fan:VariableVolume',
  'Fan:OnOff',
  'Coil:Heating:Electric',
  'Coil:Heating:Fuel',
  'Coil:Heating:Water',
  'Coil:Cooling:DX:SingleSpeed',
  'Coil:Cooling:DX:TwoSpeed',
  'Coil:Cooling:Water',
  'Controller:OutdoorAir',
  'AirLoopHVAC:OutdoorAirSystem',
  'OutdoorAir:Mixer',
  'SetpointManager:Scheduled',
  'SetpointManager:SingleZone:Reheat',
  'PlantLoop',
  'Pump:ConstantSpeed',
  'Pump:VariableSpeed',
  'Boiler:HotWater',
  'Chiller:Electric:EIR',
  'CoolingTower:SingleSpeed',
  'Output:Variable',
  'Output:Meter',
  'Output:Table:Monthly',
  'Output:Table:SummaryReports',
  'OutputControl:Table:Style',
];

/** Keywords used in IDF field values */
const KEYWORDS = [
  'Yes',
  'No',
  'On',
  'Off',
  'True',
  'False',
  'autocalculate',
  'autosize',
  'Continuous',
  'Discrete',
  'Any Number',
  'Hourly',
  'Timestep',
  'Daily',
  'Monthly',
  'RunPeriod',
  'Annual',
  'SummerDesignDay',
  'WinterDesignDay',
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Holiday',
  'CustomDay1',
  'CustomDay2',
  'AllDays',
  'Weekdays',
  'Weekends',
  'AllOtherDays',
];

/** IDF Monarch tokenizer definition */
export const idfTokensProvider: languages.IMonarchLanguage = {
  defaultToken: 'invalid',
  tokenPostfix: '.idf',

  // Case insensitive
  ignoreCase: true,

  // Common class names
  classes: COMMON_CLASSES,

  // Keywords
  keywords: KEYWORDS,

  // Operators and delimiters
  operators: [',', ';'],

  // Number patterns
  digits: /\d+/,
  floatDigits: /\d*\.\d+([eE][+-]?\d+)?/,

  tokenizer: {
    root: [
      // Whitespace
      { include: '@whitespace' },

      // Comments (must come before other rules)
      [/!-.*$/, 'comment.doc'],
      [/!.*$/, 'comment'],

      // Class names (at start of line or after semicolon)
      [
        /^([A-Za-z][A-Za-z0-9:_-]*)\s*(,)/,
        [
          {
            cases: {
              '@classes': 'type.identifier',
              '@default': 'type',
            },
          },
          'delimiter',
        ],
      ],

      // Field values
      { include: '@fieldValue' },

      // Delimiters
      [/[,]/, 'delimiter'],
      [/[;]/, 'delimiter.semicolon'],
    ],

    whitespace: [[/[ \t\r\n]+/, 'white']],

    fieldValue: [
      // Numbers (including scientific notation)
      [/-?\d*\.\d+([eE][+-]?\d+)?/, 'number.float'],
      [/-?\d+([eE][+-]?\d+)?/, 'number'],

      // Keywords
      [
        /[A-Za-z][A-Za-z0-9_-]*/,
        {
          cases: {
            '@keywords': 'keyword',
            '@default': 'string',
          },
        },
      ],

      // Wildcards and special values
      [/\*/, 'constant'],

      // Time/date patterns (e.g., "Through: 12/31")
      [/Through:\s*\d+\/\d+/, 'string.date'],
      [/For:\s*[A-Za-z,\s]+/, 'string.date'],
      [/Until:\s*\d+:\d+/, 'string.date'],
      [/Interpolate:\s*[A-Za-z]+/, 'string.date'],
    ],
  },
};
