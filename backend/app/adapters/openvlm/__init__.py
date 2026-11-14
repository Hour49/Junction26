"""Open-weights models served by us in the EU (vLLM on Verda, Finland) behind the Gemini ports.

Every step that calls Gemini can run on an open model instead, chosen per step in settings
(provider `eu`; default `gemini`, so nothing changes until a step is switched):

- `client.py`: one OpenAI-compatible chat client (key in the Authorization header, retries on
  429 and 5xx only, every other failure an `OpenVlmError` whose message is safe to show).
- `rooms.py`: the room reader. `OpenVlmRoomModel` is a `RoomModel` (the Gemini reader's port), so
  arm G4's prompt, page encoding, reply parsing and disk cache are reused as they are;
  `OpenVlmRoomExtractor` is the `Extractor`.
- `decider.py`: `OpenVlmDecider` is a `Decider` (the Gemini Decisions port) that answers each
  closed question with the probability of every option, read from the model's token log
  probabilities. G1main's count distributions (the count swap and the answer confidence) and
  the sheet-kind signal run on it unchanged.

On an API error nothing falls back to Gemini: the step's own "not available" path runs and the
trace says why. Evidence and A/B numbers: .agents/exp/eu.md.
"""
