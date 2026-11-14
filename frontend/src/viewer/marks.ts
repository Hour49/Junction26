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

/** A badge's size in CSS px for its text (bold 12 px monospace, 5 px padding, 2 px border). */
export function badgeSize(text: string): { w: number; h: number } {
  return { w: Math.max(24, Math.ceil(text.length * 7.2) + 14), h: 24 };
}

export interface PlacedLabel {
  x: number; // centre, frame px
  y: number;
  w: number;
  h: number;
  text: string;
  leader: boolean; // off its box centre: draw a line from the mark to it
}

const RINGS = 12;
const GAP = 1; // px of clearance between two badges

/**
 * Where each badge goes so no two overlap (the rule of the backend's evidence_render.place_labels,
 * simplified): smallest box first; the box centre, then a 5 x 5 grid inside the box nearest the
 * centre, then rings around the box in 8 directions; full text first, then the number only.
 * null: no free spot on the page.
 */
export function placeLabels(
  labels: readonly { box: readonly number[]; full: string; short: string }[],
  W: number,
  H: number,
): (PlacedLabel | null)[] {
  const out: (PlacedLabel | null)[] = labels.map(() => null);
  const taken: PlacedLabel[] = [];
  const px = (b: readonly number[]) => [
    (b[0] ?? 0) * W,
    (b[1] ?? 0) * H,
    (b[2] ?? 0) * W,
    (b[3] ?? 0) * H,
  ];
  const area = (b: readonly number[]) => ((b[2] ?? 0) - (b[0] ?? 0)) * ((b[3] ?? 0) - (b[1] ?? 0));
  const order = labels
    .map((_, i) => i)
    .sort((a, b) => area(labels[a]?.box ?? []) - area(labels[b]?.box ?? []));
  const free = (x: number, y: number, w: number, h: number) =>
    x - w / 2 >= 0 &&
    y - h / 2 >= 0 &&
    x + w / 2 <= W &&
    y + h / 2 <= H &&
    taken.every(
      (t) => Math.abs(x - t.x) >= (w + t.w) / 2 + GAP || Math.abs(y - t.y) >= (h + t.h) / 2 + GAP,
    );
  for (const i of order) {
    const label = labels[i];
    if (!label) continue;
    const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = px(label.box);
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    const texts = label.full === label.short ? [label.full] : [label.full, label.short];
    for (const text of texts) {
      const { w, h } = badgeSize(text);
      const grid: [number, number][] = [];
      for (let a = 1; a <= 5; a++)
        for (let b = 1; b <= 5; b++)
          grid.push([x0 + ((x1 - x0) * a) / 6, y0 + ((y1 - y0) * b) / 6]);
      grid.sort((p, q) => Math.hypot(p[0] - cx, p[1] - cy) - Math.hypot(q[0] - cx, q[1] - cy));
      const inside = grid.filter(
        ([x, y]) => x - w / 2 >= x0 && x + w / 2 <= x1 && y - h / 2 >= y0 && y + h / 2 <= y1,
      );
      const rings: [number, number][] = [];
      for (let ring = 0; ring < RINGS; ring++)
        for (let step = 0; step < 8; step++) {
          const angle = (2 * Math.PI * step) / 8 - Math.PI / 2; // from up, clockwise
          const gap = 2 + ring * h;
          rings.push([
            cx + Math.cos(angle) * ((x1 - x0) / 2 + w / 2 + gap),
            cy + Math.sin(angle) * ((y1 - y0) / 2 + h / 2 + gap),
          ]);
        }
      const spot = [[cx, cy] as [number, number], ...inside, ...rings].find(([x, y]) =>
        free(x, y, w, h),
      );
      if (spot) {
        const placed = {
          x: spot[0],
          y: spot[1],
          w,
          h,
          text,
          leader: spot[0] !== cx || spot[1] !== cy,
        };
        out[i] = placed;
        taken.push(placed);
        break;
      }
    }
  }
  return out;
}
