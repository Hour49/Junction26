import { useEffect, useRef, useState } from 'react';
import { errorText } from '../api';
import { fileName, scanRows, toCsv } from './csv';
import { loadScan } from './scan';
import './export.css';

/** How long "Exported" stays on the button (export.md EX-12). */
export const DONE_MS = 1500;

type State =
  { at: 'idle' } | { at: 'busy' } | { at: 'done'; name: string } | { at: 'failed'; detail: string };

function download(text: string, name: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

const Glyph = ({ done }: { done: boolean }) => (
  <svg className="export-glyph" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
    {done ? (
      <path d="M4.5 10.5l3.5 3.5 7.5-8" />
    ) : (
      <path d="M10 3v9m-3.5-3.5L10 12l3.5-3.5M4 14.5V16h12v-1.5" />
    )}
  </svg>
);

/** The header's "Export": the whole scan of `projectId` as one CSV (docs/specs/frontend/export.md). */
export function ExportButton({ projectId, pack }: { projectId: string; pack: string | null }) {
  const [state, setState] = useState<State>({ at: 'idle' });
  const abort = useRef<AbortController | null>(null);
  const timer = useRef<number | undefined>(undefined);
  useEffect(
    () => () => {
      abort.current?.abort();
      window.clearTimeout(timer.current);
    },
    [],
  );

  const run = () => {
    if (state.at === 'busy') return;
    window.clearTimeout(timer.current);
    const controller = new AbortController();
    abort.current = controller;
    setState({ at: 'busy' });
    loadScan(projectId, pack, controller.signal).then(
      (scan) => {
        const name = fileName(scan.project.name, new Date());
        download(toCsv(scanRows(scan)), name);
        setState({ at: 'done', name });
        timer.current = window.setTimeout(() => {
          setState({ at: 'idle' });
        }, DONE_MS);
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ at: 'failed', detail: errorText(error).detail });
      },
    );
  };

  const busy = state.at === 'busy';
  const label = { idle: 'Export', busy: 'Preparing…', done: 'Exported', failed: 'Export failed' }[
    state.at
  ];
  return (
    <span className="export">
      <button
        type="button"
        className="header-pill export-button v-press"
        data-state={state.at}
        aria-label="Export scan as CSV"
        aria-disabled={busy || undefined}
        aria-busy={busy || undefined}
        title={
          busy
            ? "Loading the scan's data"
            : state.at === 'failed'
              ? state.detail
              : 'Download everything the scan read as one CSV'
        }
        onClick={run}
      >
        <Glyph done={state.at === 'done'} />
        <span className="export-label">{label}</span>
      </button>
      <span className="export-sr" role="status">
        {state.at === 'done' ? `Exported ${state.name}` : ''}
      </span>
      {state.at === 'failed' && (
        <span className="export-error" role="alert">
          Export failed: {state.detail}. Press Export to try again.
        </span>
      )}
    </span>
  );
}
