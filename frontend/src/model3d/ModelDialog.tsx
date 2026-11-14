import { useLayoutEffect, useRef, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import type { Highlight } from '../api';
import { ModelView } from './ModelView';

/** The 3D view in a modal (model-3d.md part 2), as fe-viewer's SourcePreview: Esc and Close close it, Tab stays
 * inside; the opener puts focus back. */
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
  const card = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    card.current?.querySelector<HTMLElement>('.vw-modal-close')?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = overflow;
    };
  }, []);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    else if (e.key === 'Tab') {
      const items = [
        ...(card.current?.querySelectorAll<HTMLElement>('button, [tabindex="0"]') ?? []),
      ];
      const k = items.indexOf(document.activeElement as HTMLElement);
      const to = e.shiftKey ? (k <= 0 ? items.length - 1 : k - 1) : (k + 1) % items.length;
      e.preventDefault();
      items[to]?.focus();
    }
  };

  return createPortal(
    <div
      className="vw-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={card}
        className="vw-modal-card m3-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`3D view: ${label}`}
        onKeyDown={onKeyDown}
      >
        <div className="vw-modal-head">
          <span className="m3-dialog-name">{label}</span>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press vw-btn-soft vw-modal-close"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <ModelView projectId={projectId} fileId={fileId} name={label} highlight={highlight} />
      </div>
    </div>,
    document.body,
  );
}
