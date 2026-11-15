// Run: node --test demo/vellum/  (the generator on a tiny made-up dataset; the real Stoa data is never committed)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const STEM = 'site1_bldg1_floor1';

function dataset() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'stoa-gen-'));
  const src = path.join(root, 'data', 'swiss_dwellings');
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(root, 'questions.jsonl'), JSON.stringify({
    path: `data/swiss_dwellings/${STEM}.pdf`, question: 'How many doors are drawn on this floor plan?', answer: 3, unit: 'count', type: 'count',
  }) + '\n');
  fs.writeFileSync(path.join(src, 'LICENSE.md'), 'All files: CC-BY-4.0. Credit: test.\n');
  fs.writeFileSync(path.join(src, `${STEM}.pdf`), '%PDF-1.4 not a real page');
  fs.writeFileSync(path.join(src, `${STEM}.png`), 'not a real image');
  return root;
}

// Without pypdfium2 the PDF gets no page image, and the conflicts and issues (placed on that image) show an empty
// box with only their numbered marks. The generator must refuse instead of writing that page.
test('the generator stops when the floor PDF cannot be rendered', () => {
  const root = dataset(), out = path.join(root, 'out');
  const run = `import runpy, sys; sys.modules['pypdfium2'] = None; sys.modules['PIL'] = None
sys.argv = ['make_stoa_demo.py', '--dataset', ${JSON.stringify(root)}, '--floor', '${STEM}', '--out', ${JSON.stringify(out)},
            '--picks', ${JSON.stringify(path.join(root, 'no-picks.json'))}]
runpy.run_path(${JSON.stringify(path.join(__dirname, 'make_stoa_demo.py'))}, run_name='__main__')`;
  const r = spawnSync('python3', ['-I', '-c', run], { encoding: 'utf8' });
  try {
    assert.notEqual(r.status, 0, `exited 0: ${r.stdout}`);
    assert.match(r.stderr, /has no page image.*pypdfium2/);
    assert.equal(fs.existsSync(path.join(out, 'data.js')), false);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
