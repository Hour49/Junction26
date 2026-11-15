// Hover explanations for the ingest and account screens (docs/ui-tooltips.md, P1 and P2 rows of "Home / upload",
// "Ingest progress", "File trace and triage", "Account"). Two short sentences at most; plain words.
import type { FileStatus, StageTrace } from '../api';

type FileState = FileStatus['state'];
type Stage = StageTrace['stage'];

export const INGEST_TIPS = {
  // Home / upload
  sample: 'A small made-up flat with 11 files. Click it to see Vellum work from start to finish.',
  formats:
    'IFC and DXF are CAD and BIM files. Drawn PDFs are read exactly; scanned PDFs and photos are read by AI.',
  // Project screen
  view: 'Simple shows progress and results. Advanced shows every step and the log.',
  filesThrough: 'Files that finished reading, out of all the files found.',
  drawingsReady: 'Drawings you can ask questions about. One file can hold several drawings.',
  setAside:
    'Files Vellum skipped because they are not drawings, such as photos of people or spreadsheets. Open Documents to see why.',
  openWorkspace: 'Opens the first drawing with its plan and a question box.',
  conflicts: 'A conflict means two methods measured the same thing and got different numbers.',
  // File trace and triage
  reused: 'This exact file was read before, so Vellum reused the result.',
  stages: 'The steps this file went through, with the time each took and what it did.',
  endsAs: 'The measured counts and areas that came out of this file.',
  openDrawing: 'Opens the plan with a question box.',
  chance:
    'How sure the first check is that this file is a floor plan. The method says how it guessed.',
  yourCall: 'Say whether this file belongs to the project. Your answer replaces the guess.',
  needName: 'Type your name first: it is recorded with your call.',
  // Account
  workspaces: 'A workspace is one uploaded project and everything read from it.',
};

/** P1: what each file state word means. Queued and running explain themselves. */
export const STATE_TIPS: Record<FileState, string> = {
  queued: '',
  running: '',
  ready: 'Read and ready to use.',
  flagged: 'Read, but two methods disagree or something looks off. Check it before you rely on it.',
  text_only: 'Only its text was read. Nothing on it was measured.',
  set_aside: 'Not a drawing, so Vellum skipped it.',
};

/** P1: one short line per trace stage. */
export const STAGE_TIPS: Record<Stage, string> = {
  unpack: 'Open the upload and list its files.',
  hash: 'Take a fingerprint of the file, to spot a file read before.',
  identify: 'Work out what kind of file this is.',
  group: 'Put the pages of one drawing together.',
  route: 'Pick the reader that fits this file.',
  cache: 'This file was read before: reuse that result.',
  normalise: 'Straighten the page and fix the scale.',
  extract: 'Read the walls, rooms, doors and text.',
  second_count: 'Measure the same quantities a second way, to check the first.',
  takeoff: 'Add up the quantities.',
  write: 'Save the drawing model.',
};
