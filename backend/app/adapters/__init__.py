"""The adapters: everything that touches the outside (files, PDF and image libraries, output
formats, later an LLM or a partner API). Each one implements a port that core declares.

- A pipeline port (app/core/pipeline/ports.py, app/core/answering/ports.py): write the adapter
  here, add its name to the Literal in app/settings.py and a case in app/composition.py. The
  do-nothing implementations are in hello.py; tests pass their own fakes.
- An outside service (docs/ENGINEERING.md section 1): `<service>.py` holds the client class (the
  only SDK import, key from Settings, timeouts) and a `Fake<Service>` with recorded responses.
"""
