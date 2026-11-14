"""One lock for every pdfium call in the process: pdfium is not thread-safe, not even on two
different documents (pypdfium2's README), and the API renders pages on request threads while
ingest reads PDFs on its own thread. Hold `PDFIUM` around any pypdfium2 use."""

import threading

PDFIUM = threading.RLock()
