import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  answer,
  answerArea,
  answerConfidence,
  answerModel,
  answerRefused,
  drawing,
  error as errorJson,
  takeoff,
} from '../api/fixtures';
import type { AnswerView, MarkView, QuantityConflict, Row } from '../api/types';

type LegendEntry = AnswerView['proof']['legend'][number];
import { methodName } from '../api/format';
import { PageViewer } from './PageViewer';

const badges = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>('.vw-badge')];
const frameOf = (c: HTMLElement) => c.querySelector<HTMLElement>('.vw-frame');
const colour = (el: Element | undefined) =>
  (el as HTMLElement | undefined)?.style.getPropertyValue('--vw-c');

function viewer(a: AnswerView, extra: Partial<Parameters<typeof PageViewer>[0]> = {}) {
  return render(
    <PageViewer
      file={a.file}
      pages={a.pages}
      marks={a.marks}
      credit={null}
      unit={a.unit}
      legend={a.proof.legend}
      {...extra}
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('PageViewer: page and frame', () => {
  it('VW-1 asks for width 1600 in an 800 px frame at dpr 1', () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(800);
    viewer(answer);
    const img = screen.getByAltText('Page 1 of plans/flat-a.pdf');
    expect(img.getAttribute('src')).toBe('/api/drawings/adeefbbcc17559fc/pages/1.png?width=1600');
  });

  it('VW-4 before load: aspect ratio, loading text, aria-busy, marks already drawn', () => {
    const { container } = viewer(answer);
    const frame = frameOf(container);
    expect(frame?.style.aspectRatio).toBe('600 / 400');
    expect(screen.getByText('Loading page 1…')).toBeTruthy();
    expect(frame?.getAttribute('aria-busy')).toBe('true');
    expect(badges(container)).toHaveLength(2);
  });

  it('VW-5 after load the loading text is gone and aria-busy is not true', () => {
    const { container } = viewer(answer);
    fireEvent.load(screen.getByAltText('Page 1 of plans/flat-a.pdf'));
    expect(screen.queryByText('Loading page 1…')).toBeNull();
    expect(frameOf(container)?.getAttribute('aria-busy')).not.toBe('true');
  });

  it('VW-6 a failed page shows the API error and Try again sets the src again', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(errorJson), { status: 404 })),
    );
    vi.stubGlobal('fetch', fetchMock);
    viewer(answer);
    const img = screen.getByAltText('Page 1 of plans/flat-a.pdf');
    const src = img.getAttribute('src');
    fireEvent.error(img);
    await screen.findByText('Page 1 could not be loaded: no drawing 0123456789abcdef (not-found)');
    expect(fetchMock).toHaveBeenCalledWith(src);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => {
      expect(screen.queryByText(/could not be loaded/)).toBeNull();
    });
    expect(screen.getByAltText('Page 1 of plans/flat-a.pdf').getAttribute('src')).toBe(src);
  });

  it('VW-9 no marks: page shown, no badge, no shape, no legend', () => {
    const { container } = viewer(answerRefused);
    expect(screen.getByAltText('Page 1 of plans/flat-a.pdf')).toBeTruthy();
    expect(badges(container)).toHaveLength(0);
    expect(container.querySelectorAll('svg rect, svg polygon')).toHaveLength(0);
    expect(container.querySelector('.vw-legend')).toBeNull();
  });

  it('VW-10 the image alt names the page and the file', () => {
    render(<PageViewer file={drawing.file} pages={drawing.pages} marks={[]} credit={null} />);
    expect(screen.getByAltText('Page 1 of plans/flat-a.pdf')).toBeTruthy();
  });
});

describe('PageViewer: marks', () => {
  it('VW-11 two numbered badges, badge 1 at its box centre', () => {
    const { container } = viewer(answer);
    const [b1, b2] = badges(container);
    expect(b1?.textContent).toBe('1');
    expect(b2?.textContent).toBe('2');
    expect(parseFloat(b1?.style.left ?? '')).toBeCloseTo(50, 1);
    expect(parseFloat(b1?.style.top ?? '')).toBeCloseTo(25, 1);
  });

  it('VW-12 polygons from the fixture pairs, rects from boxes', () => {
    const area = viewer(answerArea).container;
    const polys = [...area.querySelectorAll('svg polygon')];
    expect(polys).toHaveLength(answerArea.marks.length);
    expect(polys[0]?.getAttribute('points')).toBe(
      (answerArea.marks[0]?.polygon ?? []).map(([x, y]) => `${String(x)},${String(y)}`).join(' '),
    );
    cleanup();
    const count = viewer(answer).container;
    const rect = count.querySelector('svg rect');
    const [x0, y0, x1, y1] = answer.marks[0]?.box ?? [0, 0, 0, 0];
    expect(Number(rect?.getAttribute('x'))).toBe(x0);
    expect(Number(rect?.getAttribute('y'))).toBe(y0);
    expect(Number(rect?.getAttribute('width'))).toBeCloseTo(x1 - x0, 6);
    expect(Number(rect?.getAttribute('height'))).toBeCloseTo(y1 - y0, 6);
  });

  it('VW-13 overlay viewBox, preserveAspectRatio and non-scaling strokes', () => {
    const { container } = viewer(answerArea);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe('0 0 1 1');
    expect(svg?.getAttribute('preserveAspectRatio')).toBe('none');
    const shapes = [...container.querySelectorAll('svg rect, svg polygon, svg line')];
    expect(shapes.length).toBeGreaterThan(0);
    for (const s of shapes) expect(s.getAttribute('vector-effect')).toBe('non-scaling-stroke');
  });

  it('VW-14 badges show values for m2 and not for count or null', () => {
    expect(badges(viewer(answerArea, { unit: 'm2' }).container)[0]?.textContent).toBe(
      '1 · 22.40 m²',
    );
    cleanup();
    expect(badges(viewer(answer, { unit: 'count' }).container).map((b) => b.textContent)).toEqual([
      '1',
      '2',
    ]);
    cleanup();
    expect(badges(viewer(answer, { unit: null }).container).map((b) => b.textContent)).toEqual([
      '1',
      '2',
    ]);
  });

  it('VW-21 legend colours per label; accent without a legend', () => {
    const stroke = (c: HTMLElement, i: number) => colour(c.querySelectorAll('svg polygon')[i]);
    const withLegend = viewer(answerArea).container;
    expect(stroke(withLegend, 0)).toBe('#d62728');
    expect(stroke(withLegend, 1)).toBe('#1f77b4');
    cleanup();
    const plain = viewer(answerArea, { legend: null }).container;
    const accent = stroke(plain, 0);
    expect(accent).toBe('var(--v-accent)');
    expect(stroke(plain, 1)).toBe(accent);
    expect(accent).not.toBe('#d62728');
    cleanup();
    const bad = viewer(answerArea, {
      legend: answerArea.proof.legend.map((e) => ({ ...e, colour: 'url(x)' })),
    }).container;
    expect(stroke(bad, 0)).toBe(accent);
  });

  it('R1-3-2 a one-entry legend colours every mark, whatever its label', () => {
    const [entry] = answerArea.proof.legend as [LegendEntry];
    const { container } = viewer(answerArea, {
      legend: [{ ...entry, label: 'room', colour: '#1f77b4', count: 2 }],
    });
    const polys = [...container.querySelectorAll('svg polygon')];
    expect(polys.map(colour)).toEqual(['#1f77b4', '#1f77b4']);
    expect(badges(container).map(colour)).toEqual(['#1f77b4', '#1f77b4']);
  });

  it('VW-26 strings from files render as text', () => {
    const evil = '<img src=x onerror=alert(1)>';
    const marks: MarkView[] = answer.marks.map((m) => ({ ...m, label: evil }));
    const { container } = render(
      <PageViewer
        file={evil}
        pages={answer.pages}
        marks={marks}
        credit={evil}
        legend={[{ label: evil, colour: '#d62728', count: 2, unlocated: 0, note: null }]}
      />,
    );
    expect(container.querySelectorAll('img')).toHaveLength(1);
    expect(screen.getAllByText(evil, { exact: false }).length).toBeGreaterThan(0);
  });
});

describe('PageViewer: legend, caption, pages', () => {
  it('VW-27 the legend names the states on the page in words', () => {
    const { container } = viewer(answer);
    const legend = container.querySelector('.vw-legend');
    expect(legend?.textContent).toContain('counted');
    expect(legend?.textContent).not.toContain('rejected');
    cleanup();
    const [m1, m2] = answer.marks as [MarkView, MarkView];
    const mixed = viewer(answer, { marks: [m1, { ...m2, state: 'rejected', n: null }] }).container;
    const text = mixed.querySelector('.vw-legend')?.textContent ?? '';
    expect(text).toContain('counted');
    expect(text).toContain('rejected by a surveyor');
  });

  it('VW-29 credit under the page, or "none recorded"; file name either way', () => {
    viewer(answer, { credit: 'Plan © Example, CC BY 4.0' });
    expect(screen.getByText('Credit: Plan © Example, CC BY 4.0')).toBeTruthy();
    expect(screen.getByText('plans/flat-a.pdf')).toBeTruthy();
    cleanup();
    render(<PageViewer file={drawing.file} pages={drawing.pages} marks={[]} credit={null} />);
    expect(screen.getByText('Credit: none recorded for this file')).toBeTruthy();
    expect(screen.getByText('plans/flat-a.pdf')).toBeTruthy();
  });

  it('VW-33 one page: no page switcher', () => {
    const { container } = render(
      <PageViewer file={drawing.file} pages={drawing.pages} marks={[]} credit={null} />,
    );
    expect(container.querySelector('.vw-switcher')).toBeNull();
    expect(screen.queryByText(/Page 1 of 1/)).toBeNull();
  });
});

const [door1, door2] = answer.marks as [MarkView, MarkView];
const [kitchen, reduit] = answerArea.marks as [MarkView, MarkView];
const rejected: MarkView = { ...door2, state: 'rejected', n: null };
const added: MarkView = {
  ...door1,
  id: 'a1',
  n: 3,
  state: 'added',
  label: null,
  ref: null,
  polygon: null,
};
const excluded: MarkView = {
  ...reduit,
  id: 'x1',
  n: null,
  state: 'excluded',
  label: 'Balkon',
  reason: 'outdoor room',
};
const conflictRow = takeoff.quantities.find((q) => q.key === 'area:room|name=1.01') as Row;
const conflict = conflictRow.conflict as QuantityConflict;
const badgeOf = (c: HTMLElement, text: string) => badges(c).find((b) => b.textContent === text);

describe('PageViewer: mark states', () => {
  it('VW-15 rejected: ×, dotted outline, two crossing lines, words in the label', () => {
    const { container } = viewer(answer, { marks: [door1, rejected] });
    const b = badgeOf(container, '×');
    expect(b?.getAttribute('aria-label')).toBe('door, rejected by a surveyor');
    const rects = container.querySelectorAll('svg rect');
    expect(rects[1]?.getAttribute('stroke-dasharray')).toBe('2 3');
    expect(container.querySelectorAll('svg line.vw-cross')).toHaveLength(2);
  });

  it('VW-16 added: +n, dashed outline, words in the label', () => {
    const { container } = viewer(answer, { marks: [door1, added] });
    const b = badgeOf(container, '+3');
    expect(b?.getAttribute('aria-label')).toBe('Mark 3: item, added by a surveyor');
    expect(container.querySelectorAll('svg rect')[1]?.getAttribute('stroke-dasharray')).toBe('6 3');
  });

  it('VW-17 excluded: –, hatch fill, the reason in the label', () => {
    const { container } = viewer(answerArea, { marks: [kitchen, excluded] });
    const b = badgeOf(container, '–');
    expect(b?.getAttribute('aria-label')).toBe('Balkon, left out by the rule: outdoor room');
    expect(container.querySelectorAll('svg polygon')[1]?.getAttribute('fill')).toMatch(/^url\(#/);
  });
});

describe('PageViewer: conflict readings', () => {
  it('VW-19 tags A and B at the reading boxes, listed in the legend', () => {
    const { container } = viewer(answerArea, { marks: conflictRow.marks, conflict, unit: 'm2' });
    const tags = [...container.querySelectorAll<HTMLElement>('.vw-tag')];
    expect(tags.map((t) => t.textContent)).toEqual(['A', 'B']);
    expect(tags.every((t) => t.tagName !== 'BUTTON')).toBe(true);
    // shortcut: tags sit at the box's top-left corner, not its centre (spec VW-19), so tag A does not cover badge 1.
    const [bx0, by0] = conflict.values[1]?.box ?? [0, 0];
    expect(parseFloat(tags[1]?.style.left ?? '')).toBeCloseTo(bx0 * 100, 1);
    expect(parseFloat(tags[1]?.style.top ?? '')).toBeCloseTo(by0 * 100, 1);
    const legend = container.querySelector('.vw-legend')?.textContent ?? '';
    expect(legend).toContain(`A: ${methodName('polygon_x_scale')} read 22.40 m²`);
    expect(legend).toContain(`B: ${methodName('printed_label')} read 30.00 m²`);
  });

  it('R3 VW-19 conflict readings name the method in words, never the API id', () => {
    const { container } = viewer(answerArea, { marks: conflictRow.marks, conflict, unit: 'm2' });
    const legend = container.querySelector('.vw-legend')?.textContent ?? '';
    expect(legend).not.toMatch(/polygon_x_scale|printed_label/);
    expect(methodName('polygon_x_scale')).not.toBe('polygon_x_scale');
  });

  it('VW-20 a reading with no box draws no tag but stays in the legend', () => {
    const noBox: QuantityConflict = {
      ...conflict,
      values: conflict.values.map((v, i) => (i === 1 ? { ...v, box: null } : v)),
    };
    const { container } = viewer(answerArea, { marks: [], conflict: noBox, unit: 'm2' });
    expect([...container.querySelectorAll('.vw-tag')].map((t) => t.textContent)).toEqual(['A']);
    expect(container.querySelector('.vw-legend')?.textContent).toContain(
      `B: ${methodName('printed_label')} read 30.00 m²`,
    );
  });
});

describe('PageViewer: placement and legend notes', () => {
  it('VW-25 marks on a missing page or outside the page are not drawn and are counted', () => {
    const { container } = viewer(answer, { marks: [door1, { ...door2, page: 3 }] });
    expect(badges(container)).toHaveLength(1);
    expect(container.querySelector('.vw-legend')?.textContent).toContain(
      '1 mark(s) could not be placed',
    );
    cleanup();
    const out = viewer(answer, { marks: [door1, { ...door2, box: [0.9, 0.2, 1.2, 0.3] }] });
    expect(badges(out.container)).toHaveLength(1);
    expect(out.container.querySelector('.vw-legend')?.textContent).toContain(
      '1 mark(s) could not be placed',
    );
  });

  it('VW-28 legend notes and unlocated items are said in words', () => {
    const note = '2 counted without a mark (second reader)';
    const withNote = viewer(answerConfidence, {
      legend: answerConfidence.proof.legend.map((e) => ({ ...e, note })),
    });
    expect(withNote.container.querySelector('.vw-legend')?.textContent).toContain(note);
    cleanup();
    const doorRow = takeoff.quantities.find((q) => q.key === 'door') as Row;
    const un = viewer(answer, { marks: doorRow.marks, legend: null, unlocated: { door: 2 } });
    expect(un.container.querySelector('.vw-legend')?.textContent).toContain(
      '2 door counted without a mark',
    );
    cleanup();
    const none = viewer(answer, { marks: doorRow.marks, legend: null, unlocated: {} });
    expect(none.container.querySelector('.vw-legend')?.textContent).not.toContain('without a mark');
  });

  it('VW-30 the caption says how an image page was made upright', () => {
    const [p1] = drawing.pages as [(typeof drawing.pages)[number]];
    const page = {
      ...p1,
      normalised: {
        exif: 6,
        rotated: 90,
        deskew_deg: 1.5,
        rectified: true,
        quad: null,
        width: 3024,
        height: 4032,
      },
    };
    render(<PageViewer file={drawing.file} pages={[page]} marks={[]} credit={null} />);
    expect(
      screen.getByText(
        'shown upright: EXIF turn applied, turned 90°, deskewed 1.5°, perspective corrected',
      ),
    ).toBeTruthy();
  });
});

describe('PageViewer: selection, highlight, keyboard', () => {
  it('VW-35 clicking a badge or a polygon selects its mark', () => {
    const onSelect = vi.fn();
    const { container } = viewer(answer, { onSelect });
    fireEvent.click(badgeOf(container, '2') as HTMLElement);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('m2');
    cleanup();
    const area = viewer(answerArea, { onSelect });
    fireEvent.click(area.container.querySelectorAll('svg polygon')[1] as Element);
    expect(onSelect).toHaveBeenLastCalledWith('m2');
  });

  it('VW-36 badges are native buttons in mark order; Escape clears the selection', () => {
    const onSelect = vi.fn();
    const { container } = viewer(answer, { onSelect, selected: 'm1' });
    const bs = badges(container);
    expect(bs.map((b) => b.textContent)).toEqual(['1', '2']);
    for (const b of bs) {
      expect(b.tagName).toBe('BUTTON');
      expect(b.getAttribute('type')).toBe('button');
      expect(b.tabIndex).toBe(0);
    }
    // Enter and Space activate a native button as a click; jsdom has no key activation.
    fireEvent.click(bs[0] as HTMLElement);
    expect(onSelect).toHaveBeenLastCalledWith('m1');
    fireEvent.keyDown(bs[0] as HTMLElement, { key: 'Escape' });
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it('VW-37 the selected mark is pressed and said in one line', () => {
    const { container, rerender } = viewer(answer, { selected: 'm1' });
    const [b1, b2] = badges(container);
    expect(b1?.getAttribute('aria-pressed')).toBe('true');
    expect(b2?.getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByText('1 · door · counted')).toBeTruthy();
    const restored: MarkView = { ...excluded, id: 'x2', n: 1, state: 'counted' };
    rerender(
      <PageViewer
        file={answerArea.file}
        pages={answerArea.pages}
        marks={[excluded, restored]}
        credit={null}
        selected="x1"
      />,
    );
    expect(screen.getByText('– · Balkon · left out by the rule: outdoor room')).toBeTruthy();
    rerender(
      <PageViewer
        file={answerArea.file}
        pages={answerArea.pages}
        marks={[excluded, restored]}
        credit={null}
        selected="x2"
      />,
    );
    expect(
      screen.getByText('1 · Balkon · counted (the rule left it out: outdoor room)'),
    ).toBeTruthy();
    cleanup();
    const conf = viewer(answerConfidence, { selected: 'm1' });
    conf.container.querySelector('.vw-zoom')?.remove(); // its "100%" is the zoom level
    expect(conf.container.textContent).not.toMatch(/confidence|probab|score|0\.87|87|%/i);
  });

  it('VW-38 the highlighted mark has a 4 px outline and a ring', () => {
    const { container } = viewer(answer, { highlighted: 'm2' });
    const rects = container.querySelectorAll('svg rect');
    expect(rects[0]?.getAttribute('stroke-width')).toBe('2');
    expect(rects[1]?.getAttribute('stroke-width')).toBe('4');
    expect(badgeOf(container, '2')?.classList.contains('vw-hot')).toBe(true);
    expect(badgeOf(container, '1')?.classList.contains('vw-hot')).toBe(false);
  });

  it('VW-39 pointer and focus on a badge report hover', () => {
    const onHover = vi.fn();
    const { container } = viewer(answer, { onHover });
    const b1 = badgeOf(container, '1') as HTMLElement;
    fireEvent.pointerEnter(b1);
    expect(onHover).toHaveBeenLastCalledWith('m1');
    fireEvent.pointerLeave(b1);
    expect(onHover).toHaveBeenLastCalledWith(null);
    fireEvent.focus(b1);
    expect(onHover).toHaveBeenLastCalledWith('m1');
    fireEvent.blur(b1);
    expect(onHover).toHaveBeenLastCalledWith(null);
  });
});

const twoPages = () => {
  const [p1] = answer.pages as [AnswerView['pages'][number]];
  return [p1, { ...p1, page: 2, url: p1.url.replace('/1.png', '/2.png') }];
};
const imgSrc = () => screen.getByRole('img', { hidden: true }).getAttribute('src') ?? '';

describe('PageViewer: errors and empty', () => {
  it('VW-7 a page that fails on the network says so', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    );
    viewer(answer);
    fireEvent.error(screen.getByAltText('Page 1 of plans/flat-a.pdf'));
    await screen.findByText('Page 1 could not be loaded: network error');
  });

  it('VW-8 no pages: no image, the building-model text', () => {
    const { container } = viewer(answerModel);
    expect(container.querySelector('img')).toBeNull();
    expect(
      screen.getByText('This drawing has no page to show: it is a building model.'),
    ).toBeTruthy();
  });
});

describe('PageViewer: zoom', () => {
  it('VW-3 zoom raises the served width and never lowers it', () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(800);
    viewer(answer);
    const zoomIn = screen.getByRole<HTMLButtonElement>('button', { name: 'Zoom in' });
    fireEvent.click(zoomIn);
    expect(imgSrc()).toMatch(/width=1600$/);
    fireEvent.click(zoomIn);
    expect(imgSrc()).toMatch(/width=3200$/);
    fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
    expect(imgSrc()).toMatch(/width=3200$/);
  });

  it('VW-41 +, − and Fit step 100/200/400 %, with the frame scaled', () => {
    const { container } = viewer(answer);
    const zoomIn = screen.getByRole<HTMLButtonElement>('button', { name: 'Zoom in' });
    const zoomOut = screen.getByRole<HTMLButtonElement>('button', { name: 'Zoom out' });
    expect(screen.getByText('100%')).toBeTruthy();
    expect(zoomOut.disabled).toBe(true);
    fireEvent.click(zoomIn);
    expect(screen.getByText('200%')).toBeTruthy();
    expect(frameOf(container)?.style.width).toBe('200%');
    fireEvent.click(zoomIn);
    expect(screen.getByText('400%')).toBeTruthy();
    expect(zoomIn.disabled).toBe(true);
    fireEvent.click(zoomOut);
    expect(screen.getByText('200%')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
    expect(screen.getByText('100%')).toBeTruthy();
    expect(zoomOut.disabled).toBe(true);
  });
});

describe('PageViewer: several pages', () => {
  it('VW-32 the switcher counts marks per page and moves between pages', () => {
    const { container } = viewer(answer, { pages: twoPages() });
    expect(screen.getByText('Page 1 of 2 · 2 marks')).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Previous page' }).disabled).toBe(
      true,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(imgSrc()).toMatch(/\/pages\/2\.png\?width=/);
    expect(badges(container)).toHaveLength(0);
    expect(screen.getByText('Page 2 of 2 · 0 marks')).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Next page' }).disabled).toBe(
      true,
    );
  });

  it('VW-34 selecting a mark on another page switches to it; highlighting does not', () => {
    const marks = [door1, { ...door2, page: 2 }];
    const { rerender } = viewer(answer, { pages: twoPages(), marks });
    expect(screen.getByText('Page 1 of 2 · 1 mark')).toBeTruthy();
    const props = { file: answer.file, pages: twoPages(), marks, credit: null };
    rerender(<PageViewer {...props} highlighted="m2" />);
    expect(screen.getByText('Page 1 of 2 · 1 mark')).toBeTruthy();
    rerender(<PageViewer {...props} highlighted="m2" selected="m2" />);
    expect(screen.getByText('Page 2 of 2 · 1 mark')).toBeTruthy();
  });
});

describe('PageViewer: adding a mark', () => {
  const rect = { left: 0, top: 0, width: 600, height: 400, right: 600, bottom: 400, x: 0, y: 0 };

  it('VW-42 with onPick a click on the page picks a box; a badge click selects', () => {
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      ...rect,
      toJSON: () => rect,
    });
    const onPick = vi.fn();
    const onSelect = vi.fn();
    const { container } = viewer(answer, { onPick, onSelect });
    fireEvent.click(frameOf(container) as HTMLElement, { clientX: 300, clientY: 200 });
    expect(onPick).toHaveBeenCalledTimes(1);
    const [pageNo, box] = onPick.mock.calls[0] as [number, number[]];
    expect(pageNo).toBe(1);
    [0.485, 0.4775, 0.515, 0.5225].forEach((v, i) => {
      expect(box[i]).toBeCloseTo(v, 6);
    });
    fireEvent.click(badgeOf(container, '1') as HTMLElement);
    expect(onSelect).toHaveBeenLastCalledWith('m1');
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it('VW-43 without onPick a click on the page calls nothing', () => {
    const onSelect = vi.fn();
    const { container } = viewer(answer, { onSelect });
    fireEvent.click(frameOf(container) as HTMLElement, { clientX: 10, clientY: 10 });
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe('PageViewer: label placement (R2-qa-1-3)', () => {
  it('R2-qa-1-3 VW-46 a narrow frame shows numbers only; wide shows values; aria-labels unchanged', () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(1440);
    const wide = badges(viewer(answerArea, { unit: 'm2' }).container);
    expect(wide.map((b) => b.textContent)).toEqual(['1 · 22.40 m²', '2 · 2.49 m²']);
    const wideLabels = wide.map((b) => b.getAttribute('aria-label'));
    cleanup();
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(358);
    const narrow = badges(viewer(answerArea, { unit: 'm2', selected: 'm1' }).container);
    expect(narrow.map((b) => b.textContent)).toEqual(['1', '2']);
    expect(narrow.map((b) => b.getAttribute('aria-label'))).toEqual(wideLabels);
    expect(screen.getByText('1 · Küche · 22.40 m² · counted')).toBeTruthy();
  });

  it('R2-qa-1-3 VW-47 rendered badges never intersect at 358 px on 19 rooms', () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(358);
    const marks: MarkView[] = Array.from({ length: 19 }, (_, i) => {
      const x0 = 0.2 + (i % 5) * 0.06;
      const y0 = 0.2 + Math.floor(i / 5) * 0.06;
      return {
        ...kitchen,
        id: `m${String(i + 1)}`,
        n: i + 1,
        box: [x0, y0, x0 + 0.06, y0 + 0.06],
        polygon: null,
      };
    });
    const { container } = viewer(answerArea, { marks, unit: 'm2' });
    const W = 358;
    const H = (W * 400) / 600;
    const rects = badges(container).map((b) => ({
      x: (parseFloat(b.style.left) * W) / 100,
      y: (parseFloat(b.style.top) * H) / 100,
      w: parseFloat(b.style.width),
      h: parseFloat(b.style.height),
    }));
    expect(rects.length).toBeGreaterThanOrEqual(15);
    rects.forEach((a, i) => {
      expect(a.w).toBeGreaterThan(0);
      for (const b of rects.slice(i + 1))
        expect(
          Math.abs(a.x - b.x) >= (a.w + b.w) / 2 - 0.2 ||
            Math.abs(a.y - b.y) >= (a.h + b.h) / 2 - 0.2,
        ).toBe(true);
    });
  });
});

// vitest runs in frontend/; under jsdom import.meta.url is not a file URL
const css = readFileSync('src/viewer/viewer.css', 'utf8');
const meta = (c: HTMLElement) => c.querySelector('.vw-pagemeta')?.textContent ?? '';
const page1 = drawing.pages[0] as AnswerView['pages'][number];
const onDrawing = (page: object = {}, extra: Partial<Parameters<typeof PageViewer>[0]> = {}) =>
  render(
    <PageViewer
      file={drawing.file}
      pages={[{ ...page1, ...page }]}
      marks={[]}
      credit={null}
      {...extra}
    />,
  ).container;

describe('PageViewer: Vellum (screen 4)', () => {
  it('VW-48 file in .vw-name, meta at the end of the page meta line, no "Drawing" label', () => {
    const c = onDrawing({}, { meta: 'PDF vector · vector route' });
    expect(c.querySelector('.vw')?.hasAttribute('aria-label')).toBe(false);
    expect(c.querySelector('.vw-name')?.textContent).toBe('plans/flat-a.pdf');
    expect(meta(c).endsWith('Page 1 · PDF vector · vector route')).toBe(true);
    cleanup();
    expect(meta(onDrawing({}, { meta: '' })).endsWith('Page 1')).toBe(true);
    cleanup();
    expect(meta(onDrawing()).endsWith('Page 1')).toBe(true);
  });

  it('VW-50 the class line lists legend entries with a count, as text', () => {
    const items = (c: HTMLElement) =>
      [...c.querySelectorAll('.vw-classes li')].map((li) => li.textContent);
    const door = viewer(answer).container;
    expect(items(door)).toEqual(['DOOR · 2']);
    expect(door.querySelector('[data-pending="ClassKey.layer"]')).toBeNull();
    cleanup();
    const area = items(viewer(answerArea).container);
    expect(area).toContain('KÜCHE · 1');
    expect(area.join()).not.toMatch(/LAYER|BLOCK/);
    expect(area.join()).not.toContain('BALKON');
    cleanup();
    expect(viewer(answer, { legend: null }).container.querySelector('.vw-classes')).toBeNull();
    cleanup();
    expect(viewer(answer, { marks: [] }).container.querySelector('.vw-classes')).toBeNull();
    cleanup();
    const evil = '<b>x</b>';
    const c = viewer(answer, {
      legend: [{ label: evil, colour: '#d62728', count: 2, unlocated: 0, note: null }],
    }).container;
    expect(c.querySelector('.vw-classes b')).toBeNull();
    expect(c.querySelector('.vw-classes')?.textContent).toContain('<B>X</B>');
  });

  it('VW-51 the page meta line names the page and how it was made upright', () => {
    const c = onDrawing();
    expect(meta(c)).toBe('1:100 · Page 1'); // drawing.json: storey null, scale_text "1:100"
    expect(c.querySelector('[data-pending]')).toBeNull();
    cleanup();
    const two = viewer(answer, { pages: twoPages() }).container;
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(meta(two).endsWith('Page 2')).toBe(true);
    cleanup();
    const normalised = {
      exif: 6,
      rotated: 90,
      deskew_deg: 1.5,
      rectified: true,
      quad: null,
      width: 3024,
      height: 4032,
    };
    expect(
      meta(onDrawing({ normalised })).endsWith(
        'Page 1 · shown upright: EXIF turn applied, turned 90°, deskewed 1.5°, perspective corrected',
      ),
    ).toBe(true);
  });

  it('VW-52 counted badges are filled in their class colour; rejected and excluded are open', () => {
    const { container } = viewer(answerArea);
    const [b1, b2] = badges(container);
    expect([colour(b1), colour(b2)]).toEqual(['#d62728', '#1f77b4']);
    for (const b of [b1, b2]) expect(b?.classList.contains('vw-badge--filled')).toBe(true);
    const polys = [...container.querySelectorAll('svg polygon')];
    expect(polys.map(colour)).toEqual(['#d62728', '#1f77b4']);
    cleanup();
    expect(badges(viewer(answerArea, { legend: null }).container).map(colour)).toEqual([
      'var(--v-accent)',
      'var(--v-accent)',
    ]);
    cleanup();
    const rej = viewer(answer, { marks: [door1, rejected] }).container;
    const x = badgeOf(rej, '×');
    expect(x?.classList.contains('vw-badge--open')).toBe(true);
    expect(colour(x)).toBe('var(--v-muted)');
    expect(colour(rej.querySelectorAll('svg rect')[1])).toBe('var(--v-muted)');
    cleanup();
    const exc = viewer(answerArea, { marks: [kitchen, excluded] }).container;
    const dash = badgeOf(exc, '–');
    expect(dash?.classList.contains('vw-badge--open')).toBe(true);
    expect(colour(dash)).toBe('var(--v-muted)');
    expect(colour(exc.querySelectorAll('svg polygon')[1])).toBe('var(--v-muted)');
  });

  it('VW-53 viewer.css uses only tokens, has press feedback and turns it off for reduced motion', () => {
    const plain = css.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(plain).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    expect(plain).toContain('var(--v-');
    expect(plain).toContain('var(--vw-c)');
    expect(plain).toMatch(/\.vw-badge:active\s*\{[^}]*scale\(0\.97\)/);
    expect(plain).toMatch(/prefers-reduced-motion:\s*reduce\)\s*\{[^@]*\.vw-badge:active/);
  });

  it('VW-54 the mark line shows the selected mark, else the highlighted one', () => {
    const line = (c: HTMLElement) => c.querySelector('.vw-selection')?.textContent;
    expect(line(viewer(answer, { highlighted: 'm2' }).container)).toBe('2 · door · counted');
    cleanup();
    expect(line(viewer(answer, { highlighted: 'm2', selected: 'm1' }).container)).toBe(
      '1 · door · counted',
    );
    cleanup();
    expect(viewer(answer).container.querySelector('.vw-selection')).toBeNull();
  });

  it('VW-55 one shared exclusion reason names the excluded item; swatches per state', () => {
    const out = (id: string, reason: string): MarkView => ({ ...excluded, id, reason });
    const legendText = (marks: MarkView[]) => {
      const c = viewer(answerArea, { marks }).container;
      const items = [...c.querySelectorAll('figcaption.vw-legend li')];
      return { c, texts: items.map((li) => li.textContent) };
    };
    const same = legendText([kitchen, out('x1', 'open doorway'), out('x2', 'open doorway')]);
    expect(same.texts).toContain('counted');
    expect(same.texts).toContain('open doorway, left out by the rule');
    expect(same.c.querySelector('li .vw-swatch.vw-swatch--counted')).not.toBeNull();
    expect(same.c.querySelector('li .vw-swatch.vw-swatch--excluded')).not.toBeNull();
    cleanup();
    const mixed = legendText([kitchen, out('x1', 'open doorway'), out('x2', 'outdoor room')]);
    expect(mixed.texts).toContain('left out by the rule');
  });

  it('VW-57 storey and scale_text come from the page; a null one is left out', () => {
    expect(meta(onDrawing({ storey: 'Floor 3', scale_text: '1:50' }))).toBe(
      'Floor 3 · 1:50 · Page 1',
    );
    cleanup();
    expect(meta(onDrawing({ storey: null, scale_text: null }))).toBe('Page 1');
  });

  it('VW-59 a scale not read off the sheet says how it was got', () => {
    const scale = (status: string, text: string | null) => ({
      scale_text: text,
      scale: { status, text, ratio: null, source: null },
    });
    expect(meta(onDrawing(scale('estimated', '1:100')))).toBe('1:100 (estimated) · Page 1');
    cleanup();
    expect(meta(onDrawing(scale('not_to_scale', null)))).toBe('not to scale · Page 1');
    cleanup();
    expect(meta(onDrawing(scale('no_scale', null)))).toBe('no scale · Page 1');
    cleanup();
    expect(meta(onDrawing(scale('scaled', '1:50')))).toBe('1:50 · Page 1');
  });
});

const why = 'only 1 of 2 readers saw this door';
const ask = (text: string) => `Please double-check: ${text}`;
const frameRect = () => {
  const rect = { left: 0, top: 0, width: 600, height: 400, right: 600, bottom: 400, x: 0, y: 0 };
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    ...rect,
    toJSON: () => rect,
  });
};
const legendItems = (c: HTMLElement) =>
  [...c.querySelectorAll('figcaption.vw-legend li')].map((li) => li.textContent);

describe('PageViewer: double-check (disputed places)', () => {
  it('VW-60 a disputed mark: ? tag, same name, the why as its description, a dispute outline', () => {
    const { container } = viewer(answer, {
      disputed: [{ markId: 'm2', page: 1, box: door2.box, why }],
    });
    const b2 = screen.getByRole('button', { name: 'Mark 2: door, counted' });
    expect(b2.classList.contains('vw-badge--disputed')).toBe(true);
    expect(b2.querySelectorAll('.vw-q-tag')).toHaveLength(1);
    expect(b2.querySelector('.vw-q-tag')?.getAttribute('aria-hidden')).toBe('true');
    const describedBy = b2.getAttribute('aria-describedby') ?? '';
    expect(document.getElementById(describedBy)?.textContent).toBe(ask(why));
    const b1 = screen.getByRole('button', { name: 'Mark 1: door, counted' });
    expect(b1.classList.contains('vw-badge--disputed')).toBe(false);
    expect(b1.hasAttribute('aria-describedby')).toBe(false);
    const outlines = container.querySelectorAll('svg rect.vw-dispute');
    expect(outlines).toHaveLength(1);
    const [x0, , x1] = door2.box;
    expect(Number(outlines[0]?.getAttribute('width'))).toBeGreaterThan(x1 - x0);
  });

  it('VW-61 hover and focus show the why as a tooltip; leave, blur and Escape hide it', () => {
    viewer(answer, { disputed: [{ markId: 'm2', page: 1, box: door2.box, why }] });
    const b2 = screen.getByRole('button', { name: 'Mark 2: door, counted' });
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.pointerEnter(b2);
    expect(screen.getByRole('tooltip').textContent).toBe(ask(why));
    fireEvent.pointerLeave(b2);
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.focus(b2);
    expect(screen.getByRole('tooltip').textContent).toBe(ask(why));
    fireEvent.blur(b2);
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.focus(b2);
    fireEvent.keyDown(b2, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('VW-62 a place no mark covers: a ? button with the why, toggled by click, never over a badge', () => {
    const boxWhy = 'reader A saw a door here, reader B did not';
    const { container } = viewer(answer, {
      disputed: [{ markId: null, page: 1, box: [0.7, 0.6, 0.8, 0.7], why: boxWhy }],
    });
    const q = screen.getByRole('button', { name: ask(boxWhy) });
    expect(q.textContent).toBe('?');
    expect(container.querySelectorAll('svg rect.vw-dispute')).toHaveLength(1);
    fireEvent.click(q);
    expect(screen.getByRole('tooltip').textContent).toBe(ask(boxWhy));
    fireEvent.click(q);
    expect(screen.queryByRole('tooltip')).toBeNull();
    cleanup();
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(358);
    const marks: MarkView[] = Array.from({ length: 19 }, (_, i) => {
      const x0 = 0.2 + (i % 5) * 0.06;
      const y0 = 0.2 + Math.floor(i / 5) * 0.06;
      return {
        ...kitchen,
        id: `m${String(i + 1)}`,
        n: i + 1,
        box: [x0, y0, x0 + 0.06, y0 + 0.06],
        polygon: null,
      };
    });
    const boxes = [0, 1, 2].map((i) => ({
      markId: null,
      page: 1,
      box: [0.26 + i * 0.06, 0.26, 0.3 + i * 0.06, 0.3],
      why: `w${String(i)}`,
    }));
    const many = viewer(answerArea, { marks, unit: 'm2', disputed: boxes }).container;
    const W = 358;
    const H = (W * 400) / 600;
    const rectOf = (b: HTMLElement) => ({
      x: (parseFloat(b.style.left) * W) / 100,
      y: (parseFloat(b.style.top) * H) / 100,
      w: parseFloat(b.style.width),
      h: parseFloat(b.style.height),
    });
    const qs = [...many.querySelectorAll<HTMLElement>('.vw-q')].map(rectOf);
    expect(qs.length).toBeGreaterThan(0);
    for (const a of qs)
      for (const b of badges(many).map(rectOf))
        expect(
          Math.abs(a.x - b.x) >= (a.w + b.w) / 2 - 0.2 ||
            Math.abs(a.y - b.y) >= (a.h + b.h) / 2 - 0.2,
        ).toBe(true);
  });

  it('VW-63 the legend counts places to double-check, here, on other pages and not shown', () => {
    const here = viewer(answer, { disputed: [{ markId: 'm2', page: 1, box: door2.box, why }] });
    expect(legendItems(here.container)).toContain('1 to double-check');
    expect(here.container.querySelector('.vw-swatch--doubt')).not.toBeNull();
    cleanup();
    const marks = [door1, { ...door2, page: 2 }];
    viewer(answer, {
      pages: twoPages(),
      marks,
      disputed: [{ markId: 'm2', page: 2, box: door2.box, why }],
    });
    expect(legendItems(document.body)).toContain('1 to double-check on page 2');
    expect(
      screen.getByText(/^Page 1 of 2 · 1 mark/).textContent.endsWith(' · 1 to double-check'),
    ).toBe(true);
    cleanup();
    viewer(answer, {
      pages: twoPages(),
      disputed: [{ markId: null, page: 2, box: [0.1, 0.1, 0.2, 0.2], why }],
    });
    expect(legendItems(document.body)).toContain('1 to double-check on page 2');
    expect(document.querySelectorAll('.vw-q')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(document.querySelectorAll('.vw-q')).toHaveLength(1);
    cleanup();
    viewer(answer, {
      pages: twoPages(),
      disputed: [{ markId: null, box: [0.1, 0.1, 0.2, 0.2], why }],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(document.querySelectorAll('.vw-q')).toHaveLength(1);
    cleanup();
    const lost = viewer(answer, {
      disputed: [
        { markId: 'nope', page: 1, box: [0.1, 0.1, 0.2, 0.2], why },
        { markId: null, page: 1, box: [0.9, 0.2, 1.2, 0.3], why },
      ],
    });
    expect(legendItems(lost.container)).toContain('2 place(s) to double-check could not be shown');
  });

  it('VW-64 no disputed places: nothing of the double-check shows', () => {
    for (const disputed of [undefined, []]) {
      const { container } = viewer(answer, { disputed });
      expect(
        container.querySelector('.vw-dispute, .vw-q, .vw-q-tag, .vw-swatch--doubt'),
      ).toBeNull();
      expect(screen.queryByRole('tooltip')).toBeNull();
      expect(container.textContent).not.toMatch(/double-check/);
      cleanup();
    }
  });

  it('VW-65 the mark line of a disputed mark ends with its why; the why is text', () => {
    const { container } = viewer(answer, {
      selected: 'm2',
      disputed: [{ markId: 'm2', page: 1, box: door2.box, why }],
    });
    expect(container.querySelector('.vw-selection')?.textContent).toBe(
      `2 · door · counted · ${ask(why)}`,
    );
    cleanup();
    const evil = viewer(answer, {
      selected: 'm2',
      disputed: [{ markId: 'm2', page: 1, box: door2.box, why: '<b>x</b>' }],
    }).container;
    expect(evil.querySelector('.vw-selection b')).toBeNull();
    expect(evil.querySelector('.vw-selection')?.textContent).toContain('<b>x</b>');
  });
});

describe('PageViewer: double-check (fix mode)', () => {
  const scrollOf = (c: HTMLElement) => c.querySelector('.vw-scroll') as HTMLElement;

  it('VW-66 mouse: a drag draws a draft and proposes its box; a short drag is a click; Escape cancels', () => {
    frameRect();
    const onAddMark = vi.fn();
    const { container } = viewer(answer, { fixMode: true, onAddMark });
    const s = scrollOf(container);
    const frame = frameOf(container) as HTMLElement;
    fireEvent.pointerDown(frame, { clientX: 100, clientY: 100, pointerType: 'mouse', button: 0 });
    fireEvent.pointerMove(s, { clientX: 200, clientY: 150, pointerType: 'mouse' });
    expect(container.querySelectorAll('svg rect.vw-draft')).toHaveLength(1);
    fireEvent.pointerUp(s, { clientX: 200, clientY: 150, pointerType: 'mouse' });
    expect(onAddMark).toHaveBeenCalledTimes(1);
    expect(onAddMark).toHaveBeenLastCalledWith([0.16667, 0.25, 0.33333, 0.375], 1);
    expect(container.querySelector('svg rect.vw-draft')).toBeNull();
    fireEvent.pointerDown(frame, { clientX: 200, clientY: 150, pointerType: 'mouse', button: 0 });
    fireEvent.pointerMove(s, { clientX: 100, clientY: 100, pointerType: 'mouse' });
    fireEvent.pointerUp(s, { clientX: 100, clientY: 100, pointerType: 'mouse' });
    expect(onAddMark).toHaveBeenLastCalledWith([0.16667, 0.25, 0.33333, 0.375], 1);
    fireEvent.pointerDown(frame, { clientX: 300, clientY: 200, pointerType: 'mouse', button: 0 });
    fireEvent.pointerUp(s, { clientX: 305, clientY: 202, pointerType: 'mouse' });
    expect(onAddMark).toHaveBeenLastCalledWith([0.485, 0.4775, 0.515, 0.5225], 1);
    expect(onAddMark).toHaveBeenCalledTimes(3);
    fireEvent.pointerDown(frame, { clientX: 100, clientY: 100, pointerType: 'mouse', button: 0 });
    fireEvent.pointerMove(s, { clientX: 200, clientY: 150, pointerType: 'mouse' });
    fireEvent.keyDown(s, { key: 'Escape' });
    expect(container.querySelector('svg rect.vw-draft')).toBeNull();
    fireEvent.pointerUp(s, { clientX: 200, clientY: 150, pointerType: 'mouse' });
    expect(onAddMark).toHaveBeenCalledTimes(3);
  });

  it('VW-67 touch: a tap proposes the 3 % square, no draft; a moving touch is a pan', () => {
    frameRect();
    const onAddMark = vi.fn();
    const { container } = viewer(answer, { fixMode: true, onAddMark });
    const s = scrollOf(container);
    const frame = frameOf(container) as HTMLElement;
    fireEvent.pointerDown(frame, { clientX: 300, clientY: 200, pointerType: 'touch' });
    fireEvent.pointerMove(s, { clientX: 302, clientY: 201, pointerType: 'touch' });
    expect(container.querySelector('svg rect.vw-draft')).toBeNull();
    fireEvent.pointerUp(s, { clientX: 302, clientY: 201, pointerType: 'touch' });
    expect(onAddMark).toHaveBeenCalledTimes(1);
    const [box, pageNo] = onAddMark.mock.calls[0] as [number[], number];
    expect(pageNo).toBe(1);
    [0.485, 0.4775, 0.515, 0.5225].forEach((v, i) => {
      expect(box[i]).toBeCloseTo(v, 6);
    });
    fireEvent.pointerDown(frame, { clientX: 300, clientY: 200, pointerType: 'touch' });
    fireEvent.pointerUp(s, { clientX: 300, clientY: 220, pointerType: 'touch' });
    expect(onAddMark).toHaveBeenCalledTimes(1);
    expect(css).not.toMatch(/touch-action/);
  });

  it('VW-68 fix mode: badges still select, shapes do not, the hint shows; without onAddMark nothing changes', () => {
    frameRect();
    const onAddMark = vi.fn();
    const onSelect = vi.fn();
    const { container } = viewer(answer, { fixMode: true, onAddMark, onSelect });
    const b1 = badgeOf(container, '1') as HTMLElement;
    fireEvent.pointerDown(b1, { clientX: 300, clientY: 100, pointerType: 'mouse', button: 0 });
    fireEvent.pointerUp(b1, { clientX: 300, clientY: 100, pointerType: 'mouse' });
    fireEvent.click(b1);
    expect(onSelect).toHaveBeenLastCalledWith('m1');
    expect(onAddMark).not.toHaveBeenCalled();
    fireEvent.click(container.querySelector('svg rect') as Element);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Click or drag on the drawing where a mark is missing')).toBeTruthy();
    expect(frameOf(container)?.classList.contains('vw-picking')).toBe(true);
    cleanup();
    const bare = viewer(answer, { fixMode: true, onSelect }).container;
    expect(screen.queryByText(/where a mark is missing/)).toBeNull();
    fireEvent.pointerDown(frameOf(bare) as HTMLElement, {
      clientX: 10,
      clientY: 10,
      pointerType: 'mouse',
      button: 0,
    });
    fireEvent.pointerUp(scrollOf(bare), { clientX: 10, clientY: 10, pointerType: 'mouse' });
    fireEvent.click(frameOf(bare) as HTMLElement, { clientX: 10, clientY: 10 });
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it('VW-69 viewer.css: dispute and draft rules use tokens; the dispute is dotted, a reading dashed', () => {
    const rule = (sel: string) => new RegExp(`\\${sel}[^{]*\\{([^}]*)\\}`).exec(css)?.[1] ?? '';
    expect(rule('.vw-dispute')).toMatch(/var\(--v-warn\)/);
    expect(rule('.vw-dispute')).toMatch(/var\(--v-warn-soft\)/);
    expect(rule('.vw-draft')).toMatch(/var\(--v-accent\)/);
    const { container } = viewer(answer, {
      conflict,
      disputed: [{ markId: 'm2', page: 1, box: door2.box, why }],
    });
    expect(container.querySelector('rect.vw-dispute')?.getAttribute('stroke-dasharray')).toBe(
      '2 3',
    );
    expect(container.querySelector('rect.vw-reading')?.getAttribute('stroke-dasharray')).toBe(
      '6 3',
    );
  });
});
