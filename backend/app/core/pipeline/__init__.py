"""Ingest: from files to one drawing model per drawing file (docs/PIPELINE.md).

One module per stage, each a small pure function: inventory (1-2), identify (3), group (4),
route (5), normalise (6), extract (7), second_count (8), rules (9), takeoff (10). `ingest.py` runs
them in order; `ports.py` declares what they need from outside; `model.py` holds what they pass on.
"""
