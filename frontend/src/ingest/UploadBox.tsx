import { useRef, useState, type DragEvent } from 'react';
import { ApiError, errorText, startSample, uploadProject, type Started } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { uploadTooLarge } from '../shell/limits';
import { amount, sizeText, uploadedKey } from './ingest';
import { PANEL } from './ui';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS } from '../shell/tips-ingest';

const ACCEPT = '.zip,.pdf,.png,.jpg,.jpeg,.ifc,.dxf,.svg,image/*';
// What a route reads today; no DWG (no reader). A scanned PDF goes to the raster reader.
const FORMATS = [
  'IFC models',
  'DXF',
  'PDF, drawn or scanned',
  'SVG',
  'PNG · JPG scans and photos',
  'ZIP archives',
];

/** An upload on its way: bytes sent of the total (XHR progress). */
type Sending = { name: string; sent: number; total: number };
/** An upload that failed: the file (for Retry), the error, and how far it got. */
type Failed = { file: File; error: unknown; at: number };

const percent = (s: Sending) => (s.total > 0 ? Math.round((100 * s.sent) / s.total) : 0);

/** What failed and where (Bogdan 2026-11-15): lost while sending, or refused by the server with its detail. */
function failedLine(f: Failed): string {
  const name = f.file.name;
  if (f.error instanceof ApiError && f.error.status > 0)
    return `The server refused ${name}: ${f.error.detail}`;
  if (f.error instanceof ApiError)
    return `The connection was lost while sending ${name} (at ${String(f.at)}%).`;
  return `Could not send ${name}: ${errorText(f.error).detail}`;
}

/** Start a project: drop or pick one file, or the sample archive. A file's upload shows its progress, then on 202
 * the app goes to the project's extraction view, which says what the server received. */
export function UploadBox() {
  const [busy, setBusy] = useState<string | null>(null);
  const [sending, setSending] = useState<Sending | null>(null);
  const [failed, setFailed] = useState<Failed | null>(null);
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
    setFailed(null);
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
    send(file);
  }

  function send(file: File) {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    setNote(null);
    setFailed(null);
    let at: Sending = { name: file.name, sent: 0, total: file.size };
    setSending(at);
    uploadProject(file, {
      onProgress: (sent, total) => {
        at = { name: file.name, sent, total };
        setSending(at);
      },
    })
      .then(
        (started) => {
          try {
            sessionStorage.setItem(
              uploadedKey(started.id),
              JSON.stringify({ name: file.name, bytes: file.size }),
            );
          } catch {
            // no storage: the extraction view just doesn't repeat it
          }
          window.location.hash = `#/p/${started.id}`;
        },
        (e: unknown) => {
          setFailed({ file, error: e, at: percent(at) });
        },
      )
      .finally(() => {
        inFlight.current = false;
        setSending(null);
      });
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    if (!inFlight.current) upload(event.dataTransfer.files);
  }

  return (
    <Card
      role="region"
      className={cn(
        PANEL,
        'grid w-full max-w-[760px] gap-6 rounded-[calc(var(--v-radius)+4px)] px-8 py-12 max-[720px]:p-5',
      )}
      aria-label="Drop drawings or an archive"
      onDragOver={(e) => {
        e.preventDefault();
      }}
      onDrop={onDrop}
    >
      <div className="grid justify-items-center gap-4 rounded-[20px] border-2 border-dashed border-border px-6 py-10">
        <svg
          className="size-12 rounded-2xl bg-accent fill-none stroke-primary stroke-2 p-3 [stroke-linecap:round] [stroke-linejoin:round]"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M12 16V4m0 0-5 5m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        <p className="v-h3">Drop a drawing or a .zip here</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button
            size="pill"
            disabled={busy !== null || sending !== null}
            onClick={() => {
              picker.current?.click();
            }}
          >
            Choose a file
          </Button>
          <input
            ref={picker}
            type="file"
            accept={ACCEPT}
            hidden
            disabled={busy !== null || sending !== null}
            onChange={(e) => {
              upload(e.target.files);
              e.target.value = '';
            }}
          />
          <Tip text={INGEST_TIPS.sample} wrap={busy !== null || sending !== null}>
            <Button
              variant="secondary"
              size="pill"
              className="font-medium"
              disabled={busy !== null || sending !== null}
              onClick={() => {
                void start('Starting the sample…', () => startSample({ fresh: true }));
              }}
            >
              Try the sample project
            </Button>
          </Tip>
        </div>
        <p className="v-caption">The sample starts from scratch each time.</p>
        {busy && (
          <p role="status" aria-live="polite">
            {busy}
          </p>
        )}
        {sending &&
          (sending.total > 0 && sending.sent >= sending.total ? (
            <p role="status" aria-live="polite">
              {`Sent ${sending.name} (${sizeText(sending.total)}): waiting for the server…`}
            </p>
          ) : (
            <div
              role="status"
              aria-live="polite"
              className="flex w-[min(100%,420px)] flex-col items-center gap-2"
            >
              <p>{`Sending ${sending.name}: ${amount(sending.sent, sending.total)} of ${sizeText(sending.total)} (${String(percent(sending))}%)`}</p>
              <progress
                className="h-2 w-full accent-primary"
                aria-label="Upload"
                max={100}
                value={percent(sending)}
              />
            </div>
          ))}
        {failed && (
          <Alert className="flex w-auto flex-wrap items-center justify-center gap-x-3 gap-y-2 border-0 bg-transparent p-0 text-[length:inherit]">
            <p>{failedLine(failed)}</p>
            <Button
              variant="secondary"
              size="pill"
              className="font-medium"
              onClick={() => {
                send(failed.file);
              }}
            >
              Retry
            </Button>
          </Alert>
        )}
        {note && <p role="alert">{note}</p>}
        {error !== null && <ErrorView error={error} />}
      </div>
      <Tip text={INGEST_TIPS.formats}>
        <ul className="flex flex-wrap justify-center gap-2" tabIndex={0} aria-label="Formats">
          {FORMATS.map((f) => (
            <Badge
              asChild
              key={f}
              variant="secondary"
              className="px-[11px] py-[5px] text-xs text-text-2"
            >
              <li>{f}</li>
            </Badge>
          ))}
        </ul>
      </Tip>
    </Card>
  );
}
