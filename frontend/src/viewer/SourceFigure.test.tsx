import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawing, projectIssues, projectReview } from '../api/fixtures';
import { cropOf, SourceFigure, type Source } from './SourceFigure';

type Box = [number, number, number, number];
function must<T>(v: T | undefined): T {
  if (v === undefined) throw new Error('fixture changed');
  return v;
}
const page = must(drawing.pages[0]);
const conflict = must(projectReview.conflicts[0]);
const v1 = must(conflict.conflict.values[0]);
const v2 = must(conflict.conflict.values[1]);
const twoPlaces: Source = {
  name: 'Flat B, ground floor',
  page,
  places: [
    { label: 'Read from the outline: 22.4 m²', box: v1.box },
    { label: 'Printed label: 30 m²', box: v2.box },
  ],
};
const issue = must(projectIssues.issues[0]);
const second: Source = {
  name: 'Flat B, copy',
  page,
  places: [{ label: 'Same room on the copy', box: [0.6, 0.6, 0.7, 0.7] }],
};

const legend = (c: HTMLElement) =>
  [...c.querySelectorAll('.vw-hl-legend li')].map((li) => li.textContent);
const dialog = () => screen.queryByRole('dialog');

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('SourceFigure', () => {
  it('VW-82 starts minimized with the numbered legend, Expand and Show source', () => {
    const { container } = render(
      <SourceFigure sources={[twoPlaces]} label="Source of conflict 1" />,
    );
    const fig = screen.getByRole('figure', { name: 'Source of conflict 1' });
    expect(fig.classList.contains('vw-src--min')).toBe(true);
    const thumb = screen.getByRole('button', { name: 'Expand the drawing' });
    expect(thumb.getAttribute('aria-expanded')).toBe('false');
    expect(legend(container)).toEqual(['1Read from the outline: 22.4 m²', '2Printed label: 30 m²']);
    expect(screen.getByRole('button', { name: 'Expand' }).getAttribute('aria-expanded')).toBe(
      'false',
    );
    expect(screen.getByRole('button', { name: 'Show source' })).toBeTruthy();
    expect(dialog()).toBeNull();
  });

  it('VW-83 Expand and the thumbnail open it in place; Minimize closes it', () => {
    render(<SourceFigure sources={[twoPlaces]} label="Source" />);
    const fig = screen.getByRole('figure');
    fireEvent.click(screen.getByRole('button', { name: 'Expand' }));
    expect(fig.classList.contains('vw-src--min')).toBe(false);
    expect(screen.getByRole('button', { name: 'Minimize' }).getAttribute('aria-expanded')).toBe(
      'true',
    );
    const thumb = screen.getByRole('button', { name: 'Minimize the drawing' });
    expect(thumb.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Minimize' }));
    expect(fig.classList.contains('vw-src--min')).toBe(true);
    // a real <button>: Enter and Space arrive as clicks
    fireEvent.click(screen.getByRole('button', { name: 'Expand the drawing' }));
    expect(fig.classList.contains('vw-src--min')).toBe(false);
    expect(thumb.tagName).toBe('BUTTON');
  });

  it('VW-84 outlines are numbered, hidden from assistive tech, placed in the crop', () => {
    const { container } = render(<SourceFigure sources={[twoPlaces]} label="Source" />);
    const hl = [...container.querySelectorAll<HTMLElement>('.vw-src-frame .vw-hl')];
    expect(hl.map((h) => h.textContent)).toEqual(['1', '2']);
    expect(hl.every((h) => h.getAttribute('aria-hidden') === 'true')).toBe(true);
    const [x0, , x1] = cropOf(twoPlaces.places);
    const want = ((((v1.box as Box)[0] - x0) / (x1 - x0)) * 100).toFixed(3);
    expect(parseFloat(must(hl[0]).style.left).toFixed(3)).toBe(want);
    cleanup();
    const poly = render(
      <SourceFigure
        sources={[
          {
            name: 'x',
            page,
            places: [{ label: issue.why, box: issue.box, polygon: issue.polygon }],
          },
        ]}
        label="Source"
      />,
    ).container;
    expect(poly.querySelector('.vw-src-frame polygon.vw-hl-poly')).toBeTruthy();
    expect(poly.querySelector('.vw-src-frame .vw-hl')?.textContent).toBe('1');
  });

  it('VW-86 no position, no places, no page, no sources', () => {
    const { container } = render(
      <SourceFigure sources={[{ name: 'x', page, places: [{ label: 'Somewhere' }] }]} label="S" />,
    );
    expect(container.querySelector('.vw-hl')).toBeNull();
    expect(legend(container)).toEqual(['1Somewhere']);
    cleanup();
    const none = render(
      <SourceFigure sources={[{ name: 'x', page, places: [] }]} label="S" />,
    ).container;
    expect(none.querySelector('.vw-hl-legend')).toBeNull();
    expect(none.querySelector('img')).toBeTruthy();
    cleanup();
    const nopic = render(
      <SourceFigure sources={[{ name: 'x', page: null, places: [] }]} label="S" />,
    ).container;
    expect(screen.getByText('No picture of this file')).toBeTruthy();
    expect(nopic.querySelector('img')).toBeNull();
    expect(screen.getByRole('button', { name: 'Show source' })).toBeTruthy();
    cleanup();
    expect(render(<SourceFigure sources={[]} label="S" />).container.innerHTML).toBe('');
  });

  it('VW-87 Show source opens the whole page; Esc and the backdrop close; focus moves', () => {
    render(<SourceFigure sources={[twoPlaces]} label="Source" />);
    const show = screen.getByRole('button', { name: 'Show source' });
    fireEvent.click(show);
    const d = screen.getByRole('dialog', { name: 'Source: Flat B, ground floor' });
    expect(d.getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(within(d).getByRole('button', { name: 'Close' }));
    const frame = d.querySelector<HTMLElement>('.vw-src-frame');
    expect(frame?.style.aspectRatio).toBe(`${String(page.width)} / ${String(page.height)}`);
    expect(d.querySelectorAll('.vw-hl')).toHaveLength(2);
    fireEvent.keyDown(d, { key: 'Escape' });
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(show);

    fireEvent.click(show);
    fireEvent.click(screen.getByRole('dialog'));
    expect(dialog()).not.toBeNull();
    fireEvent.click(document.querySelector('.vw-modal') as HTMLElement);
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(show);
  });

  it('VW-88 two sources: position, arrows wrap, keys, numbers kept, focus trapped', () => {
    render(<SourceFigure sources={[twoPlaces, second]} label="Source" />);
    fireEvent.click(screen.getByRole('button', { name: 'Show source' }));
    const d = screen.getByRole('dialog');
    const head = () => d.querySelector('.vw-modal-head')?.textContent;
    expect(head()).toContain('Flat B, ground floor · 1 of 2');
    fireEvent.click(within(d).getByRole('button', { name: 'Next source' }));
    expect(head()).toContain('Flat B, copy · 2 of 2');
    expect([...d.querySelectorAll('.vw-hl')].map((h) => h.textContent)).toEqual(['3']);
    fireEvent.click(within(d).getByRole('button', { name: 'Next source' }));
    expect(head()).toContain('1 of 2');
    fireEvent.keyDown(d, { key: 'ArrowLeft' });
    expect(head()).toContain('2 of 2');
    const close = within(d).getByRole('button', { name: 'Close' });
    const last = within(d).getByRole('button', { name: 'Next source' });
    last.focus();
    fireEvent.keyDown(d, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    close.focus();
    fireEvent.keyDown(d, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(last);
    cleanup();
    render(<SourceFigure sources={[twoPlaces]} label="Source" />);
    fireEvent.click(screen.getByRole('button', { name: 'Show source' }));
    expect(screen.queryByRole('button', { name: 'Next source' })).toBeNull();
  });

  it('VW-89 served widths for the thumbnail and the preview; image error text', () => {
    const whole: Source = { name: 'x', page, places: [] };
    const width = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(150);
    render(<SourceFigure sources={[whole]} label="S" />);
    expect(screen.getByAltText('x').getAttribute('src')).toBe(`${page.url}?width=400`);
    width.mockReturnValue(1000);
    fireEvent.click(screen.getByRole('button', { name: 'Show source' }));
    const big = within(screen.getByRole('dialog')).getByAltText('x');
    expect(big.getAttribute('src')).toBe(`${page.url}?width=1600`);
    fireEvent.error(big);
    expect(within(screen.getByRole('dialog')).getByText('Could not load the drawing')).toBeTruthy();
  });
});

describe('cropOf', () => {
  it('VW-85 pads by max(half the size, 0.08), clamps, uses polygon bounds', () => {
    expect(cropOf([])).toEqual([0, 0, 1, 1]);
    expect(cropOf([{ label: 'a' }])).toEqual([0, 0, 1, 1]);
    const c = cropOf([{ label: 'a', box: [0.4, 0.4, 0.5, 0.5] }]);
    c.forEach((v, i) => {
      expect(v).toBeCloseTo(must([0.32, 0.32, 0.58, 0.58][i]), 6);
    });
    const big = cropOf([{ label: 'a', box: [0.2, 0.3, 0.6, 0.5] }]);
    [0, 0.2, 0.8, 0.6].forEach((v, i) => {
      expect(big[i]).toBeCloseTo(v, 6);
    });
    const edge = cropOf([{ label: 'a', box: [0.95, 0, 1, 0.05] }]);
    [0.87, 0, 1, 0.13].forEach((v, i) => {
      expect(edge[i]).toBeCloseTo(v, 6);
    });
    const p = cropOf([
      {
        label: 'a',
        polygon: [
          [0.4, 0.4],
          [0.5, 0.45],
          [0.45, 0.5],
        ],
      },
    ]);
    p.forEach((v, i) => {
      expect(v).toBeCloseTo(must([0.32, 0.32, 0.58, 0.58][i]), 6);
    });
  });

  it('VW-90 viewer.css source rules use only tokens', () => {
    const css = readFileSync('src/viewer/viewer.css', 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replaceAll('var(--v-plan, #fbf8ef)', '');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    for (const sel of ['.vw-src', '.vw-hl', '.vw-hl-legend', '.vw-modal', '.vw-modal-card']) {
      expect(css).toContain(`${sel} {`);
    }
  });
});

describe('SourceFigure: image sources', () => {
  it('VW-92 a source with no page but an image shows the image, never outlines', () => {
    const { container } = render(
      <SourceFigure
        sources={[
          {
            name: 'Scan of the stair',
            page: null,
            image: '/api/files/abc/preview.png',
            places: [{ label: 'The stair', box: [0.1, 0.1, 0.2, 0.2] }],
          },
        ]}
        label="S"
      />,
    );
    expect(screen.getByAltText('Scan of the stair').getAttribute('src')).toBe(
      '/api/files/abc/preview.png',
    );
    expect(container.querySelector('.vw-hl')).toBeNull();
    expect(legend(container)).toEqual(['1The stair']);
    expect(screen.getByRole('button', { name: 'Expand the drawing' })).toBeTruthy();
    expect(screen.queryByText('No picture of this file')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show source' }));
    const d = screen.getByRole('dialog');
    expect(within(d).getByAltText('Scan of the stair')).toBeTruthy();
    expect(d.querySelector('.vw-hl')).toBeNull();
  });
});

describe('SourceFigure: demo look (re-sweep 6)', () => {
  it('VW-94 button classes, cream frames, one button row under the figure at 390', () => {
    render(<SourceFigure sources={[twoPlaces]} label="S" />);
    const expand = screen.getByRole('button', { name: 'Expand' });
    const show = screen.getByRole('button', { name: 'Show source' });
    expect(expand.classList.contains('vw-btn-plain')).toBe(true);
    expect(show.classList.contains('vw-btn-soft')).toBe(true);
    // the buttons are the figure's own row, not inside the caption, so they can wrap under it at 390
    expect(expand.closest('figcaption')).toBeNull();
    expect(expand.parentElement?.parentElement?.tagName).toBe('FIGURE');
    const css = readFileSync('src/viewer/viewer.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    const rule = (sel: string) =>
      new RegExp(`${sel.replace(/[.[\]]/g, '\\$&')}\\s*\\{([^}]*)\\}`).exec(css)?.[1] ?? '';
    expect(rule('.v-btn.vw-btn-plain')).toMatch(
      /background:\s*var\(--v-grey\)[\s\S]*font-size:\s*14px[\s\S]*font-weight:\s*500/,
    );
    expect(rule('.v-btn.vw-btn-soft')).toMatch(
      /color:\s*var\(--v-accent\)[\s\S]*font-size:\s*14px[\s\S]*font-weight:\s*600/,
    );
    expect(rule('.vw-src-thumb')).toMatch(
      /background:\s*var\(--v-plan, #fbf8ef\)[\s\S]*padding:\s*16px|padding:\s*16px[\s\S]*background:\s*var\(--v-plan, #fbf8ef\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 520px\)\s*\{[^@]*\.vw-src--min\s*\{[^}]*flex-wrap:\s*wrap[^@]*\.vw-src-btns\s*\{[^}]*flex:\s*1 0 100%/,
    );
  });
});

describe('SourceFigure: coincident badges (follow-up)', () => {
  const k = (el: Element | undefined) =>
    (el as HTMLElement | undefined)?.style.getPropertyValue('--vw-k');
  it('VW-95 two places with the same box: the second number moves aside, readable at any width', () => {
    const same: Source = {
      name: 'x',
      page,
      places: [
        { label: 'A', box: [0.4, 0.4, 0.5, 0.5] },
        { label: 'B', box: [0.4, 0.4, 0.5, 0.5] },
        { label: 'C', box: [0.4, 0.4, 0.5, 0.5] },
      ],
    };
    const { container } = render(<SourceFigure sources={[same]} label="S" />);
    const hl = [...container.querySelectorAll('.vw-src-frame .vw-hl')];
    expect(hl.map(k)).toEqual(['0', '1', '2']);
    cleanup();
    // near corners (the sample's kitchen conflict) collide on a 150 px thumbnail, not when far apart
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(150);
    const near = render(<SourceFigure sources={[twoPlaces]} label="S" />).container;
    expect([...near.querySelectorAll('.vw-src-frame .vw-hl')].map(k)).toEqual(['0', '1']);
    cleanup();
    const far = render(
      <SourceFigure
        sources={[
          {
            ...twoPlaces,
            places: [...twoPlaces.places.slice(0, 1), { label: 'far', box: [0.8, 0.8, 0.9, 0.9] }],
          },
        ]}
        label="S"
      />,
    ).container;
    expect([...far.querySelectorAll('.vw-src-frame .vw-hl')].map(k)).toEqual(['0', '0']);
    const css = readFileSync('src/viewer/viewer.css', 'utf8');
    expect(css).toMatch(/\.vw-hl b \{[^}]*left: calc\(-11px \+ var\(--vw-k, 0\) \* 24px\)/);
  });
});
