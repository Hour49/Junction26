# eval/certificate: the scripts the C1-T1 test certificate ran

Kept as they ran (ruff skips this folder). None of them is a pytest test, whatever its name: `test` in a file
name means the test split.

- `certify.py`, `certify_join.py`: the check certificate. Commands and results: docs/GOLDEN.md, "The test
  certificate (config C1-T1)".
- `test_scores.py`, `test_levels.py`, `stats.py`: the confidence levels on that certificate (docs/GOLDEN.md,
  "Confidence levels on test"; decision 0011). Copies of the scripts as run on 2026-11-14 at 17:20, with one line
  changed in each of the first two: `REPO` was the checkout's absolute path and is now the repo root found from
  the file's place. Rerun from these copies, they gave the same `levels.jsonl` and `levels-table.md`, byte for
  byte, and a `levels-table.json` with the same content (its key order changes from run to run).

## Rerun the levels

`<run>` is the stored test read, `<fixed>` the corrected certificate's folder (`certified.jsonl`,
`answers-api.jsonl`). Step 1 reads no truth and stops unless every row equals the certificate's; step 2 joins the
truth.

```bash
cd backend && PYTHONPATH=. uv run --locked python ../eval/certificate/test_scores.py \
  --run <run> --corrected <fixed> --out <out>/levels.jsonl
cd ../eval && PYTHONPATH=.:certificate uv run --locked python certificate/test_levels.py \
  --truth <test questions with truth .jsonl> --run <run> --answers <fixed>/answers-api.jsonl \
  --levels <out>/levels.jsonl --out <out> --cuts shipped,020
```

Besides the committed policy files, the scripts read gitignored files under `data/`: the two local gate models
(`data/models/arbiter/T1/`), the pinned certificate policy (`data/stoa/exp/golden22/`), and from
`data/stoa/exp/confidence/` the pre-registered thresholds (`levels-policy.json`, `levels-policy-c010.json`, each
checked by sha256) and the val tables printed next to the test numbers (`schemes.json`,
`levels-val-insample*.json`). Without `--corrected`, step 1 scores the certificate's first run instead.
