export const PRODUCT_NAME = 'Countersign';

/** Port labels for "What runs" (docs/API.md "GET /api/info" `readers`). */
export const READER_LABELS: Record<string, string> = {
  bim: 'BIM model',
  cad: 'CAD (DXF)',
  vector: 'Vector PDF',
  raster: 'Scans and photos',
  tables: 'Tables and schedules',
  second_counter: 'Second count',
  rectifier: 'Photo rectifier',
  question_parser: 'Questions',
  answer_prior: 'Answer prior',
  decisions_kind: 'Answer decisions',
};

export const OFFLINE_TEXT = 'Running offline: no API keys, no models';
