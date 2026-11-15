import { useRef, useState, type DragEvent } from 'react';
import {
  ApiError,
  errorText,
  listSamples,
  startSample,
  uploadProject,
  type SampleOption,
  type Started,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { nameTooLong, uploadTooLarge } from '../shell/limits';
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
// What a route reads today; no DWG (no reader). A scanned PDF goes to the raster reader. A DXF or SVG alone is set
// aside (no page to place its model on, API.md), so its chip says it needs its PDF.
const FORMATS = [
  'IFC models',
  'DXF with its PDF',
  'PDF, drawn or scanned',
  'SVG with its PDF',
  'PNG · JPG scans and photos',
  'ZIP archives',
];

/** An upload on its way: bytes sent of the total (XHR progress). */
type Sending = { name: string; sent: number; total: number };
/** An upload that failed: the file (for Retry), the error, and how far it got. */
type Failed = { file: File; error: unknown; at: number };

const percent = (s: Sending) => (s.total > 0 ? Math.round((100 * s.sent) / s.total) : 0);

/** Whether sending the same file again can help (QA R4-G6): not when the server refused the file itself (a 4xx
 * such as empty, too large or not a drawing), except 408 (timed out) and 429 (busy). */
function canRetry(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status < 400 || error.status >= 500) return true;
  return error.status === 408 || error.status === 429;
}

/** What failed and where (Bogdan 2026-11-15): lost while sending, or refused by the server with its detail. */
function failedLine(f: Failed): string {
  const name = f.file.name;
  // 5xx: the server (or the proxy in front of it) failed, not the file
  if (f.error instanceof ApiError && f.error.status >= 500)
    return `The server could not take ${name} right now. Retry in a moment.`; // the gateway's own words (errors.ts) would say it twice
  if (f.error instanceof ApiError && f.error.status > 0) {
    // the server's detail may name the file itself ("site.zip: the upload is empty"): say it once
    const detail = f.error.detail.startsWith(`${name}: `)
      ? f.error.detail.slice(name.length + 2)
      : f.error.detail;
    return `The server refused ${name}: ${detail}`;
  }
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
  const [samples, setSamples] = useState<SampleOption[] | null>(null);
  const { info } = useInfo();

  const startOne = (sample?: SampleOption) => {
    setSamples(null);
    const label = sample ? `Starting ${sample.title}…` : 'Starting the sample…';
    void start(label, () => startSample({ fresh: true, id: sample?.id }));
  };

  /** "Try a sample project" (Bogdan 2026-11-15): the curated samples to pick from; with none, or when the list
   * fails, the synthetic sample starts at once as before. */
  async function openSamples() {
    if (samples) {
      setSamples(null);
      return;
    }
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy('Loading the samples…');
    setError(null);
    let listed: SampleOption[] = [];
    try {
      listed = (await listSamples()).samples;
    } catch {
      // the synthetic sample below
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
    if (listed.length > 1) setSamples(listed);
    else startOne();
  }

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
    setFailed(null); // a new try replaces the last failed upload's line
    if (files.length > 1) {
      setNote(
        'Drop one file at a time. To send several, such as a DXF or SVG with its PDF, put them in one .zip.',
      );
      return;
    }
    // No limits yet (info pending or failed): the server's 413 decides.
    const refused =
      nameTooLong(file.name) ?? (info ? uploadTooLarge(file.size, info.limits) : null);
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
              aria-expanded={samples !== null}
              aria-controls="sample-options"
              onClick={() => {
                void openSamples();
              }}
            >
              Try a sample project
            </Button>
          </Tip>
        </div>
        {samples && (
          <ul
            id="sample-options"
            aria-label="Sample projects"
            className="grid w-full max-w-[640px] gap-2 sm:grid-cols-2"
            onKeyDown={(e) => {
              if (e.key === 'Escape') setSamples(null);
            }}
          >
            {samples.map((sample, i) => (
              <li key={sample.id}>
                <button
                  type="button"
                  autoFocus={i === 0}
                  className="grid h-full w-full gap-1 rounded-[var(--v-radius)] border border-border bg-card p-3 text-left hover:border-primary focus-visible:outline-2 focus-visible:outline-primary"
                  onClick={() => {
                    startOne(sample);
                  }}
                >
                  <span className="font-medium">{sample.title}</span>
                  {sample.blurb !== '' && <span className="v-caption">{sample.blurb}</span>}
                  {sample.tags.length > 0 && (
                    <span className="flex flex-wrap gap-1" aria-label="Contains">
                      {sample.tags.map((tag) => (
                        <Badge
                          key={tag}
                          variant="secondary"
                          className="px-2 py-0.5 text-[11px] text-text-2"
                        >
                          {tag}
                        </Badge>
                      ))}
                    </span>
                  )}
                  {sample.prompts.length > 0 && (
                    <span className="grid gap-0.5 text-[12px] text-text-2" aria-label="Try asking">
                      {sample.prompts.slice(0, 2).map((prompt) => (
                        <span key={prompt}>“{prompt}”</span>
                      ))}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="v-caption">A sample starts from scratch each time.</p>
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
            {canRetry(failed.error) && (
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
            )}
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
