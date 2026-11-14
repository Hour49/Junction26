import { describe, expect, it } from 'vitest';
import { answer, drawing } from '../api/fixtures';
import type { MarkView, PageView } from '../api/types';
import { markLook, normalisedNote, pickBox, pickWidth, safeColour, startPage } from './marks';

describe('marks.ts', () => {
  it('VW-2 pickWidth picks the smallest served width that covers the frame', () => {
    expect(pickWidth(300, 1, 1)).toBe(400);
    expect(pickWidth(800, 2, 1)).toBe(1600);
    expect(pickWidth(900, 2, 1)).toBe(3200);
    expect(pickWidth(900, 1, 4)).toBe(3200);
    for (const css of [0, 1, 399, 401, 1599, 1601, 5000])
      expect([400, 1600, 3200]).toContain(pickWidth(css, 1, 1));
  });

  it('VW-31 startPage: first numbered mark, else first mark, else first page', () => {
    const [p1] = drawing.pages as [PageView];
    const pages = [p1, { ...p1, page: 2 }];
    const [m1, m2] = answer.marks as [MarkView, MarkView];
    expect(
      startPage(pages, [
        { ...m1, page: 2, n: null },
        { ...m2, page: 1 },
      ]),
    ).toBe(1);
    expect(startPage(pages, [{ ...m1, page: 2, n: null, state: 'rejected' }])).toBe(2);
    expect(startPage(pages, [])).toBe(1);
  });

  it('safeColour keeps #rrggbb only', () => {
    expect(safeColour('#d62728')).toBe('#d62728');
    for (const bad of ['red', '#d6272', 'url(x)', '#d62728;x'])
      expect(safeColour(bad)).not.toBe(bad);
  });

  it('VW-18 markLook: each state has its own badge form and line style', () => {
    const states = ['counted', 'added', 'rejected', 'excluded'] as const;
    const looks = states.map((st) => markLook(st));
    expect(new Set(looks.map((l) => l.badge)).size).toBe(4);
    expect(new Set(looks.map((l) => l.line)).size).toBe(4);
  });

  it('VW-30 normalisedNote says what was done, and nothing when nothing was', () => {
    expect(normalisedNote(null)).toBe('');
    expect(
      normalisedNote({
        exif: null,
        rotated: 0,
        deskew_deg: 0,
        rectified: false,
        width: 1,
        height: 1,
      }),
    ).toBe('');
    expect(
      normalisedNote({
        exif: 6,
        rotated: 90,
        deskew_deg: 1.5,
        rectified: true,
        width: 3024,
        height: 4032,
      }),
    ).toBe('shown upright: EXIF turn applied, turned 90°, deskewed 1.5°, perspective corrected');
  });

  it('VW-42 pickBox: a square of 3 % of the page width around the point, kept inside the page', () => {
    const page = { width: 600, height: 400 };
    const box = pickBox(page, 0.5, 0.5);
    [0.485, 0.4775, 0.515, 0.5225].forEach((v, i) => {
      expect(box[i]).toBeCloseTo(v, 6);
    });
    const edge = pickBox(page, 0.001, 0.999);
    expect(edge[0]).toBe(0);
    expect(edge[2]).toBeCloseTo(0.03, 6);
    expect(edge[3]).toBe(1);
    expect(edge[3] - edge[1]).toBeCloseTo(0.045, 6);
  });
});
