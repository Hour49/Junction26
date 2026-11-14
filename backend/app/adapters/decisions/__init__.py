"""Gemini Decisions API (gemini-decision-1): count distributions for a raster page (arm G1main).

`client.py` talks to the API, `g1main.py` asks the 12 count questions and caches the reply,
`uses.py` turns them into F1main's count swap (an `Extractor` wrapper) and an answer confidence.
Evidence: .agents/exp/decide.md (val: F1main-v8 83.2%; g1main gate AUROC 0.956 vs pb_mode 0.818).
"""
