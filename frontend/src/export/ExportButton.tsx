import { useEffect, useRef, useState } from 'react';
import { errorText } from '../api';
import { fileName, scanRows, toCsv } from './csv';
import { loadScan } from './scan';
import { CheckIcon, DownloadIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tip } from '@/components/ui/tip';
import { TIPS } from '../shell/tips';
import { cn } from '@/lib/utils';

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

/** The look of the header's pills (shell.css .header-pill), plus the state colours (export.md "Look"). */
const PILL =
  'v-press min-h-12 rounded-full bg-secondary px-4 py-1 text-base font-semibold text-foreground hover:bg-secondary max-[720px]:min-w-12 max-[720px]:px-3';
const TONE: Record<State['at'], string> = {
  idle: '',
  busy: 'cursor-progress text-muted-foreground active:scale-100',
  done: 'bg-ok-soft text-ok hover:bg-ok-soft',
  failed: 'bg-danger-soft text-danger hover:bg-danger-soft',
};

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
    // order 4 in the compact header (shell.css, max-width 1100px), next to the country pill.
    <span className="relative flex-none max-[1100px]:order-4">
      <Tip
        text={busy ? "Loading the scan's data" : state.at === 'failed' ? state.detail : TIPS.export}
      >
        <Button
          className={cn(PILL, TONE[state.at])}
          data-state={state.at}
          aria-label="Export scan as CSV"
          aria-disabled={busy || undefined}
          aria-busy={busy || undefined}
          onClick={run}
        >
          {state.at === 'done' ? (
            <CheckIcon className="size-[18px]" aria-hidden="true" />
          ) : (
            <DownloadIcon className="size-[18px]" aria-hidden="true" />
          )}
          <span className="max-[720px]:hidden">{label}</span>
        </Button>
      </Tip>
      <span className="sr-only" role="status">
        {state.at === 'done' ? `Exported ${state.name}` : ''}
      </span>
      {state.at === 'failed' && (
        // Anchored under its button, right-aligned like the country popover; feedback in place, no toast.
        <span
          className="absolute top-[calc(100%+8px)] right-0 z-[11] w-max max-w-[min(320px,calc(100vw-32px))] rounded-[14px] bg-card px-3.5 py-2.5 text-[13px] leading-[1.4] text-danger shadow-[var(--v-shadow)]"
          role="alert"
        >
          Export failed: {state.detail}. Press Export to try again.
        </span>
      )}
    </span>
  );
}
