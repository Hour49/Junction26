import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tip } from '@/components/ui/tip';
import { useInfo } from '../shell/info';
import { TIPS } from '../shell/tips';

/** The photo kinds the server reads (#425 added TIFF and WebP), by type and by extension for pickers that
 * only know the file name. */
export const PHOTO_ACCEPT =
  'image/png,image/jpeg,image/tiff,image/webp,.png,.jpg,.jpeg,.tif,.tiff,.webp';

/** The question box while the pen is on (qa #430): how to type again, short enough for 390 px. */
export const PEN_ON = 'Pen on: press Esc or the pen to type';

/** Why the pen is off for a scan or photo (ui-bugs 1). */
export const CANT_DRAW =
  "You can't draw on this plan: it is a photo/scan. Drawing works on drawn PDF plans and building-model sheets.";

/** The chat's pen (ui-bugs 1): on, the question box waits while you draw on the plan; `can` false greys it out,
 * and hover, focus or a tap says why. */
export interface Pen {
  on: boolean;
  can: boolean;
  /** The backend's reason it can't (`not_drawable_reason`); the generic sentence when absent. */
  reason?: string | null;
  onToggle: () => void;
}

function PenButton({ pen }: { pen: Pen }) {
  const icon = (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        d="M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
  // qa #430: both pens carry the shared Tip (hover, focus, tap). The greyed one is aria-disabled, not disabled:
  // a disabled button gets no hover, focus or tap, so its tip could not show.
  const tip = pen.can
    ? pen.on
      ? 'Pen on: click a room or drag a rectangle. Press Esc or the pen to type again.'
      : 'Draw on the plan: click a room or drag a rectangle.'
    : pen.reason
      ? `You can't draw on this plan: ${pen.reason}.`
      : CANT_DRAW;
  return (
    <Tip text={tip}>
      <Button
        type="button"
        variant={pen.on ? 'secondary' : 'ghost'}
        size="pill-icon"
        aria-label="Draw on the plan"
        {...(pen.can ? { 'aria-pressed': pen.on } : { 'aria-disabled': true })}
        className={pen.can ? undefined : 'opacity-50'}
        onClick={pen.can ? pen.onToggle : undefined}
      >
        {icon}
      </Button>
    </Tip>
  );
}

const PHONE = '(max-width: 480px)';

/** Whether the window is phone-wide (PHONE), following resizes; false where matchMedia is missing. */
function usePhone(): boolean {
  const [phone, setPhone] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE).matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia(PHONE);
    const follow = () => {
      setPhone(query.matches);
    };
    query.addEventListener('change', follow);
    return () => {
      query.removeEventListener('change', follow);
    };
  }, []);
  return phone;
}

/** The question input; sends the trimmed question, nothing when empty, over the server's limit or while
 * an answer is pending. Before `/api/info` answers there is no limit here: the server's 422 shows. */
export function AskBox(props: {
  file: string;
  busy: boolean;
  asked: number;
  onAsk: (question: string) => void;
  /** The chat's paperclip (chat.md CH-17): shown only when passed; `attaching` disables it. */
  onAttach?: (photo: File) => void;
  attaching?: boolean;
  /** A shorter `file` for the placeholder on phones (CH-22), where the paperclip takes its room. */
  short?: string;
  /** The chat's pen (ui-bugs 1): shown only when passed; while on, typing and sending wait. */
  pen?: Pen;
}) {
  const { file, busy, asked, onAsk, onAttach, attaching = false, short, pen } = props;
  const drawing = pen?.on === true;
  const phone = usePhone();
  const [text, setText] = useState('');
  const picker = useRef<HTMLInputElement>(null);
  const limit = useInfo().info?.limits.question_chars;
  const question = text.trim();
  const tooLong = limit !== undefined && question.length > limit;
  const blocked = !question || busy || tooLong || drawing;
  // Why the send button is greyed out (a disabled button has no hover of its own).
  const sendReason = drawing
    ? TIPS.sendDrawing
    : busy
      ? TIPS.sendBusy
      : tooLong
        ? TIPS.sendTooLong
        : TIPS.sendDisabled;
  return (
    <form
      className="en-ask"
      onSubmit={(e) => {
        e.preventDefault();
        if (blocked) return;
        onAsk(question);
        setText('');
      }}
    >
      <div className="en-askpill">
        <label htmlFor="en-question" className="en-sr">
          Question
        </label>
        <input
          id="en-question"
          value={text}
          placeholder={drawing ? PEN_ON : `Ask about ${phone && short ? short : file}`}
          disabled={drawing}
          autoComplete="off"
          aria-describedby={tooLong ? 'en-too-long' : undefined}
          onChange={(e) => {
            setText(e.target.value);
          }}
        />
        {onAttach && (
          <>
            <input
              ref={picker}
              type="file"
              accept={PHOTO_ACCEPT}
              hidden
              data-testid="photo-input"
              onChange={(e) => {
                const photo = e.target.files?.[0];
                e.target.value = ''; // the same file can be picked again
                if (photo) onAttach(photo);
              }}
            />
            <Tip text={TIPS.photo}>
              <button
                type="button"
                className="en-attach v-press"
                aria-label="Add a photo"
                disabled={attaching}
                onClick={() => picker.current?.click()}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                  <path
                    d="M21 11.5l-8.6 8.6a5 5 0 01-7.1-7.1l8.6-8.6a3.5 3.5 0 015 5l-8.6 8.6a2 2 0 01-2.8-2.8l7.9-7.9"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </Tip>
          </>
        )}
        {pen && <PenButton pen={pen} />}
        <span className="en-meta">
          {asked} asked
          {limit !== undefined && ` · ${String(question.length)} / ${String(limit)}`}
        </span>
        <Tip text={blocked ? sendReason : ''} wrap className="shrink-0">
          <button type="submit" className="en-send v-press" aria-label="Ask" disabled={blocked}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path
                d="M12 19V5M5 12l7-7 7 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </Tip>
      </div>
      {tooLong && (
        <p id="en-too-long" className="en-warn en-limit" role="alert">
          Questions are at most {limit} characters.
        </p>
      )}
    </form>
  );
}
