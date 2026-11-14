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
import { PageViewer } from './PageViewer';

const badges = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>('.vw-badge')];
const frameOf = (c: HTMLElement) => c.querySelector<HTMLElement>('.vw-frame');

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
    const stroke = (c: HTMLElement, i: number) =>
      c.querySelectorAll('svg polygon')[i]?.getAttribute('stroke');
    const withLegend = viewer(answerArea).container;
    expect(stroke(withLegend, 0)).toBe('#d62728');
    expect(stroke(withLegend, 1)).toBe('#1f77b4');
    cleanup();
    const plain = viewer(answerArea, { legend: null }).container;
    const accent = stroke(plain, 0);
    expect(accent).toBeTruthy();
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
    expect(polys.map((p) => p.getAttribute('stroke'))).toEqual(['#1f77b4', '#1f77b4']);
    expect(badges(container).map((b) => b.style.borderColor)).toEqual([
      'rgb(31, 119, 180)',
      'rgb(31, 119, 180)',
    ]);
  });

  it('VW-23 badges: white background, ink text, border in the mark colour', () => {
    const { container } = viewer(answerArea);
    const [b1, b2] = badges(container);
    for (const b of [b1, b2]) {
      expect(b?.style.background).toBe('rgb(255, 255, 255)');
      expect(b?.style.color).toBe('rgb(27, 31, 39)');
    }
    expect(b1?.style.borderColor).toBe('rgb(214, 39, 40)');
    expect(b2?.style.borderColor).toBe('rgb(31, 119, 180)');
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
    expect(legend).toContain('A: polygon_x_scale read 22.40 m²');
    expect(legend).toContain('B: printed_label read 30.00 m²');
  });

  it('VW-20 a reading with no box draws no tag but stays in the legend', () => {
    const noBox: QuantityConflict = {
      ...conflict,
      values: conflict.values.map((v, i) => (i === 1 ? { ...v, box: null } : v)),
    };
    const { container } = viewer(answerArea, { marks: [], conflict: noBox, unit: 'm2' });
    expect([...container.querySelectorAll('.vw-tag')].map((t) => t.textContent)).toEqual(['A']);
    expect(container.querySelector('.vw-legend')?.textContent).toContain(
      'B: printed_label read 30.00 m²',
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
