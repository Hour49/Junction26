import type { MarkView, Normalised, PageView } from '../api/types';

export type PageWidth = 400 | 1600 | 3200;
const WIDTHS: readonly PageWidth[] = [400, 1600, 3200];

export const ACCENT = '#c8402a';
export const INK = '#1b1f27';
export const GREY = '#8a909c';

/** The smallest served page width that covers the frame's device pixels; 3200 when none does. */
export function pickWidth(cssWidth: number, dpr: number, zoom: number): PageWidth {
  return WIDTHS.find((w) => w >= cssWidth * dpr * zoom) ?? 3200;
}

/** The page to open on: the first numbered mark's, else the first mark's, else the first page. */
export function startPage(pages: readonly PageView[], marks: readonly MarkView[]): number {
  return (marks.find((m) => m.n !== null) ?? marks[0])?.page ?? pages[0]?.page ?? 1;
}

/** A legend colour goes into a style attribute: only `#rrggbb` is let through. */
export function safeColour(colour: string | undefined): string {
  return colour !== undefined && /^#[0-9a-f]{6}$/i.test(colour) ? colour : ACCENT;
}

/** A mark's state in words, for the legend and the badge label (never colour alone). */
export const STATE_WORDS: Record<MarkView['state'], string> = {
  counted: 'counted',
  added: 'added by a surveyor',
  rejected: 'rejected by a surveyor',
  excluded: 'left out by the rule',
};

/** Badge text: "n" counted, "+n" added, "×" rejected, "–" excluded. */
export function badgeText(mark: MarkView): string {
  const { badge } = markLook(mark.state);
  if (badge === '+n' || badge === 'n')
    return mark.n === null ? '–' : badge.replace('n', String(mark.n));
  return badge;
}

export type Line = 'solid' | 'dashed' | 'dotted' | 'hatched';
export const DASH: Record<Line, string | undefined> = {
  solid: undefined,
  dashed: '6 3',
  dotted: '2 3',
  hatched: '4 3',
};

/** How a state looks without colour: its badge form and its line style (viewer.md "How each mark is drawn"). */
export function markLook(state: MarkView['state']): { badge: string; line: Line } {
  if (state === 'added') return { badge: '+n', line: 'dashed' };
  if (state === 'rejected') return { badge: '×', line: 'dotted' };
  if (state === 'excluded') return { badge: '–', line: 'hatched' };
  return { badge: 'n', line: 'solid' };
}

/** What normalisation did to an image page, in words; "" when nothing was done. */
export function normalisedNote(n: Normalised | null): string {
  if (n === null) return '';
  const done = [
    n.exif != null && n.exif !== 1 ? 'EXIF turn applied' : null,
    n.rotated !== 0 ? `turned ${String(n.rotated)}°` : null,
    n.deskew_deg !== 0 ? `deskewed ${String(n.deskew_deg)}°` : null,
    n.rectified ? 'perspective corrected' : null,
  ].filter((d) => d !== null);
  return done.length > 0 ? `shown upright: ${done.join(', ')}` : '';
}

const round5 = (v: number) => Number(v.toFixed(5));

/** The box of a mark added where the user clicked: a square 3 % of the page width, shifted inside the page. */
export function pickBox(
  page: { width: number; height: number },
  x: number,
  y: number,
): [number, number, number, number] {
  const hx = 0.015;
  const hy = (hx * page.width) / page.height;
  const x0 = Math.min(Math.max(x - hx, 0), 1 - 2 * hx);
  const y0 = Math.min(Math.max(y - hy, 0), 1 - 2 * hy);
  return [round5(x0), round5(y0), round5(x0 + 2 * hx), round5(y0 + 2 * hy)];
}
