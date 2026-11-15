// The file page's facts grid at the project's viewport (QA ifc-r1 row 20, S2): a long unbreakable path in one fact
// must not squeeze the others to a letter per line, for every file kind, and nothing scrolls sideways.
import { expect, test } from '@playwright/test';
import { type FileTrace } from '../src/api';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const LONG = 'bim/bimspeed-vitoria_ald26-project.ifc';
const KINDS: FileTrace['file']['kind'][] = ['ifc', 'pdf_vector', 'pdf_scan', 'photo', 'text'];

for (const kind of KINDS) {
  test(`facts grid keeps every fact readable with a long path (${String(kind)})`, async ({
    page,
  }, testInfo) => {
    const errors = watchErrors(page);
    const offline = await noKeys(page);
    const pid = await sampleDone(page);
    // the sample's first file, dressed as the QA's IFC file: its path, source and group are the long name
    await page.route(`**/api/projects/${pid}/files/f1/trace`, async (route) => {
      const response = await route.fetch();
      const trace = (await response.json()) as FileTrace;
      trace.file = {
        ...trace.file,
        kind,
        path: LONG,
        source: LONG,
        group: LONG.replace(/\.ifc$/, ''),
      };
      await route.fulfill({ response, json: trace });
    });
    await page.goto(`/#/p/${pid}/f/f1`);
    const facts = page.locator('.ingest-facts');
    await expect(facts.getByText(LONG, { exact: true })).toBeVisible();
    const cells = await facts.locator(':scope > div').evaluateAll((divs) =>
      divs.map((d) => {
        const dt = d.querySelector('dt');
        const dd = d.querySelector('dd');
        const lines = (el: Element | null) => {
          if (!el) return 0;
          const range = document.createRange();
          range.selectNodeContents(el);
          return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size;
        };
        return {
          label: dt?.textContent ?? '',
          width: Math.round(d.getBoundingClientRect().width),
          labelLines: lines(dt),
          valueLines: lines(dd),
        };
      }),
    );
    // no cell narrower than a readable column, every label on one line
    expect(cells.filter((c) => c.width < 150)).toEqual([]);
    expect(cells.filter((c) => c.labelLines !== 1)).toEqual([]);
    // the short values fit one line; only the long path may wrap
    const short = cells.filter((c) => !['Read from', 'Group', 'Route'].includes(c.label));
    expect(short.filter((c) => c.valueLines !== 1)).toEqual([]);
    // a path breaks after its own separators: each part between them stays on one line
    const split = await facts.locator('dd').evaluateAll((dds) =>
      dds.flatMap((dd) =>
        [...dd.childNodes]
          .filter((n) => n.nodeType === Node.TEXT_NODE)
          .filter((n) => {
            const range = document.createRange();
            range.selectNodeContents(n);
            return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size > 1;
          })
          .map((n) => n.textContent),
      ),
    );
    expect(split).toEqual([]);
    if (kind === 'ifc') {
      await facts.scrollIntoViewIfNeeded();
      await shot(page, testInfo, 'file-facts-ifc', offline);
    } else {
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    }
    expect(errors).toEqual([]);
  });
}
