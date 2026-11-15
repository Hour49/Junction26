import { useState, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import type { Highlight } from '../api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { ModelView } from './ModelView';

/** The 3D view in a modal (model-3d.md part 2): Esc, Close and a click outside close it, Tab stays inside (Radix);
 * the opener puts focus back. */
export function ModelDialog({
  projectId,
  fileId,
  label,
  highlight,
  onClose,
}: {
  projectId: string;
  fileId: string;
  label: string;
  highlight: readonly Highlight[];
  onClose: () => void;
}) {
  const [open, setOpen] = useState(true);
  // a portal's key events bubble through the React tree: keep them from the plan sheet's own Esc/Tab handling
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape' || e.key === 'Tab') e.stopPropagation();
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) return;
        // closed first, so Radix's focus trap is off when the opener puts focus back (its onClose)
        flushSync(() => {
          setOpen(false);
        });
        onClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        aria-describedby={undefined}
        onKeyDown={onKeyDown}
        // the opener has put focus back: Radix must not move it to what was focused before the dialog
        onCloseAutoFocus={(e) => {
          e.preventDefault();
        }}
        className="flex max-h-[calc(100dvh-32px)] w-[min(1100px,calc(100%-32px))] max-w-none flex-col gap-3 overflow-auto rounded-[20px] border-0 bg-card p-5 text-foreground sm:max-w-none [&_.m3-stage]:h-[min(70vh,640px)]"
      >
        <div className="flex items-center justify-between gap-3">
          <DialogTitle className="min-w-0 text-base font-semibold [overflow-wrap:anywhere]">
            <span className="sr-only">3D view:</span> {label}
          </DialogTitle>
          <DialogClose asChild>
            <Button variant="secondary" size="pill" className="v-press font-medium">
              Close
            </Button>
          </DialogClose>
        </div>
        <ModelView projectId={projectId} fileId={fileId} name={label} highlight={highlight} />
      </DialogContent>
    </Dialog>
  );
}
