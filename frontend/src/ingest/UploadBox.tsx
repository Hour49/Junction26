import { useRef, useState, type DragEvent } from 'react';
import { startSample, uploadProject, type Started } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { uploadTooLarge } from '../shell/limits';

const ACCEPT = '.zip,.pdf,.png,.jpg,.jpeg,.ifc,.dxf,.svg,image/*';
// What a route reads today; no DWG (no reader).
const FORMATS = [
  'IFC models',
  'DXF',
  'Vector PDF · SVG',
  'PNG · JPG scans and photos',
  'ZIP archives',
];

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
      className="v-card v-card--hero ingest-drop"
      aria-label="Drop drawings or an archive"
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDrop={onDrop}
    >
      <div className="ingest-zone">
        <svg className="ingest-upload-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 16V4m0 0-5 5m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        <p className="v-h3">Drop a drawing or a .zip here</p>
        <div className="ingest-actions">
          <button
            type="button"
            className="v-btn v-press"
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
            className="v-btn v-btn--secondary v-press"
            disabled={busy !== null}
            onClick={() => {
              void start('Starting the sample…', () => startSample({ fresh: true }));
            }}
          >
            Try the sample project
          </button>
        </div>
        <p className="v-caption">The sample starts from scratch each time.</p>
        {busy && (
          <p role="status" aria-live="polite">
            {busy}
          </p>
        )}
        {note && <p role="alert">{note}</p>}
        {error !== null && <ErrorView error={error} />}
      </div>
      <ul className="ingest-chips" aria-label="Formats">
        {FORMATS.map((f) => (
          <li key={f} className="v-pill">
            {f}
          </li>
        ))}
      </ul>
    </section>
  );
}
