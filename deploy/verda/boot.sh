# Entrypoint of hour49-reader on a stock python:3.13-slim image (no registry needed): fetch the
# two bundles from the private bucket through presigned URLs (Verda secrets, never in the image),
# unpack them side by side, then run the server. Each step logs its time for the cold-start
# numbers. Passed to the container as `sh -c "<this file>"` by verda_serve.py.
set -e
t0=$(date +%s.%N)
mkdir -p /opt/reader
fetch() { python3 -c 'import os, shutil, sys, urllib.request; shutil.copyfileobj(urllib.request.urlopen(os.environ[sys.argv[1]], timeout=120), sys.stdout.buffer, 1 << 22)' "$1"; }
fetch READER_DEPS_URL | tar -xz -C /opt/reader &
deps=$!
fetch READER_APP_URL | tar -xz -C /opt/reader
wait "$deps"
echo "boot: bundles unpacked in $(python3 -c "import time; print(round(time.time() - $t0, 1))") s" >&2
export PYTHONPATH=/opt/reader/site READER_APP=/opt/reader
READER_MODEL=$(ls -d /opt/reader/model/*/ | head -1)
export READER_MODEL=${READER_MODEL%/}
exec python3 /opt/reader/server.py
