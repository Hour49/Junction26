// Every hover explanation in one place, keyed by where it is shown (docs/ui-tooltips.md, P1 rows).
// Two short sentences at most: what it is, what to do. Plain words; no code names.
import { statusTip } from '../engineer/format';

export const TIPS = {
  // Home / upload
  sample: 'A small made-up flat with 12 files. Click it to see Vellum work from start to finish.',
  offline:
    'No AI key is set, so Vellum uses its built-in readers only. Scans and photos may stay unread.',
  formats:
    'IFC and DXF are CAD and BIM files. Drawn PDFs are read exactly; scanned PDFs and photos are read by AI.',
  // Header
  tabDocuments:
    'Every file and drawing, and the issues that need your answer. The number is how many are waiting.',
  tabChat: 'Ask questions across all the drawings of the project.',
  tabIngest: "The project's files and how each one was read.",
  country:
    'Picks the building rules this project is pre-checked against. It is a pre-check, not a certificate.',
  export: 'Download everything Vellum read as one CSV file.',
  // Ingest progress and file trace
  drawingsReady: 'Drawings you can ask questions about. One file can hold several drawings.',
  setAside:
    'Files Vellum skipped because they are not drawings. Open Documents to see why for each file.',
  filesThrough: 'Files that finished reading, out of all the files found.',
  stateReady: 'Read and ready to use.',
  stateFlagged:
    'Read, but two methods disagree or something looks off. Check it before you rely on it.',
  stateTextOnly: 'Only its text was read. Nothing on it was measured.',
  stateSetAside: 'Not a drawing, so Vellum skipped it.',
  stages: 'The steps this file went through, with the time each took and what it did.',
  stageRoute: 'Which reader fits this file: exact CAD or vector, or AI vision.',
  stageNormalise: 'Straighten the page and fix its scale so measurements are true.',
  stageSecondCount: 'Measure the same quantities a second way, as a check.',
  stageTakeoff: 'Add up the quantities, with the counting rule for each.',
  stageStore: 'Save the drawing model so you can ask questions about it.',
  // Engineer page
  howRead:
    'How this drawing was read: exact CAD or vector, or AI vision for scans and photos. Click to see the details.',
  suggested: 'Questions Vellum knows it can answer for this drawing. Click one to ask it.',
  sendDisabled: 'Type a question first.',
  mark: 'One thing Vellum counted. The number matches the list of marks.',
  checks: 'How this number was verified: which methods measured it and whether they agree.',
  secondScore:
    'How much a second, independent reader agrees. Higher is better; it is not a probability.',
  flagged: 'Vellum read this drawing, but something looks off. Check the answer against the plan.',
  photo: 'Add a photo of a plan (png, jpeg, tiff or webp) and ask about it.',
  sendBusy: 'Wait for the answer to this question first.',
  sendTooLong: 'The question is too long. Shorten it to send it.',
  sendDrawing: 'Finish drawing on the plan first, then ask.',
  prevDrawing: 'Go to the previous drawing of this project.',
  nextDrawing: 'Go to the next drawing of this project.',
  rule: 'The written rule Vellum used to count. The small code after it is for engineers.',
  colClass: 'The kind of object, such as a wall or a door.',
  colStorey: 'The floor the object is on.',
  colGlobalId: "The object's unique id inside the building model.",
  // Answer status pill (same words as engineer/format.ts)
  status: {
    signed: statusTip('signed'),
    agree: statusTip('agree'),
    conflict: statusTip('conflict'),
    estimate: statusTip('estimate'),
    edited: statusTip('edited'),
    single: statusTip('single'),
  },
  // Documents
  issues: 'What Vellum could not decide alone and needs your answer now.',
} as const;

/** The tip for a file's state word ("" for a state without one: no tip is shown). */
export function fileStateTip(state: string): string {
  const tips: Record<string, string> = {
    ready: TIPS.stateReady,
    flagged: TIPS.stateFlagged,
    text_only: TIPS.stateTextOnly,
    set_aside: TIPS.stateSetAside,
  };
  return tips[state] ?? '';
}

export type TipKey = Exclude<keyof typeof TIPS, 'status'>;
