import { useRef, useState, type DragEvent } from 'react';
import { startSample, uploadProject, type Started } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { uploadTooLarge } from '../shell/limits';

const ACCEPT = '.zip,.pdf,.png,.jpg,.jpeg,.ifc,.dxf,.svg,image/*';

/** Start a project: drop or pick one file, or the sample archive. On 202 the app goes to the project. */
export function UploadBox() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);
  const inFlight = useRef(false);
  const picker = useRef<HTMLInputElement>(null);
  const { info } = useInfo();

  async function start(label: string, call: () => Promise<Started>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(label);
    setError(null);
    setNote(null);
    try {
      const started = await call();
      window.location.hash = `#/p/${started.id}`;
    } catch (e) {
      setError(e);
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  function upload(files: FileList | null) {
    const file = files?.[0];
    if (!files || !file) return;
    if (files.length > 1) {
      setNote('Drop one file or one zip at a time.');
      return;
    }
    // No limits yet (info pending or failed): the server's 413 decides.
    const refused = info ? uploadTooLarge(file.size, info.limits) : null;
    if (refused) {
      setError(null);
      setNote(refused);
      return;
    }
    void start(`Uploading ${file.name}…`, () => uploadProject(file));
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    if (!inFlight.current) upload(event.dataTransfer.files);
  }

  return (
    <section
      className="ingest-drop"
      aria-label="Start a project"
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDrop={onDrop}
    >
      <h1>Drop a project here: one .zip, or one plan as PDF, image, IFC, DXF or SVG</h1>
      <div className="ingest-actions">
        <button
          type="button"
          className="btn"
          disabled={busy !== null}
          onClick={() => {
            picker.current?.click();
          }}
        >
          Choose a file
        </button>
        <input
          ref={picker}
          type="file"
          accept={ACCEPT}
          hidden
          disabled={busy !== null}
          onChange={(e) => {
            upload(e.target.files);
            e.target.value = '';
          }}
        />
        <button
          type="button"
          className="btn primary"
          disabled={busy !== null}
          onClick={() => {
            void start('Starting the sample…', () => startSample({ fresh: true }));
          }}
        >
          Try the sample project
        </button>
      </div>
      <p className="ingest-hint">The sample starts from scratch each time.</p>
      {busy && (
        <p role="status" aria-live="polite">
          {busy}
        </p>
      )}
      {note && <p role="alert">{note}</p>}
      {error !== null && <ErrorView error={error} />}
    </section>
  );
}
