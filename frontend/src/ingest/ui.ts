// The ingest screens' shared Tailwind class strings (what ingest.css held before the shadcn migration).
import { CARD } from '../documents/ui';

/** The page wrapper: paragraphs and lists reset as ingest.css's `.ingest p/ul/ol` did, also in the parts it hosts
 * (conflicts list, Advanced). Paragraphs here never set their own margin: this rule outranks a single utility. */
export const PAGE =
  '[&_ol]:m-0 [&_ol]:list-none [&_ol]:p-0 [&_p]:m-0 [&_p]:[overflow-wrap:anywhere] [&_ul]:m-0 [&_ul]:list-none [&_ul]:p-0';
/** shell.css's .v-card on shadcn's Card (24 px, 20 px on a phone). */
export const PANEL = `${CARD} p-6 max-[720px]:p-5`;
/** A phone tap target: links and summaries at least 44 px tall (IN-70). */
export const TAP = 'inline-flex min-h-11 items-center';
export const MUTED = 'text-sm text-muted-foreground';
/** A summary of a fold: 44 px, the pointer, no extra marker styling. */
export const SUMMARY = 'flex min-h-11 cursor-pointer items-center';
