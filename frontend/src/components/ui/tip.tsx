import * as React from 'react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip';

/** The look of the surveyor's "Settled by rule" tip: dark rounded box, 12px text, 240px wide. */
const LOOK =
  'w-60 max-w-[240px] rounded-xl px-3 py-2 text-left text-xs leading-snug font-normal text-balance';

interface TipProps {
  /** The words (two short sentences at most); see `shell/tips.ts`. */
  text: string;
  children: React.ReactElement;
  /**
   * Wrap the child in a focusable span that carries the tip. Use it for a disabled button (a disabled
   * button gets no hover or focus) and for plain text such as a pill or a number.
   */
  wrap?: boolean;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

/** What a tap activates: a tap on one of these (enabled) is its action, not a request for the tip. */
const CONTROL =
  'button, a[href], input, select, textarea, summary, [role="button"], [role="link"], [role="tab"], [role="checkbox"], [role="switch"], [role="menuitem"], [role="option"]';

function onControl(target: EventTarget) {
  const hit = target instanceof Element ? target.closest(CONTROL) : null;
  return hit !== null && !hit.matches(':disabled, [aria-disabled="true"]');
}

/**
 * One hover explanation for any control. Shows on hover, keyboard focus and a tap on a label, number or locked
 * control; Escape or the next tap closes it. A tap on a working control (a link, an enabled button) does what it
 * does and shows no tip. Radix adds `role="tooltip"` and `aria-describedby`, and moves the box away from the
 * screen edges.
 */
export function Tip({ text, children, wrap = false, side = 'bottom', className }: TipProps) {
  const [open, setOpen] = React.useState(false);
  // On touch there is no hover: the tap's click alone decides. From the touch's pointerdown, Radix's own changes
  // are ignored: the focus a tap gives would open the tip (on a link too), and Radix's click handler, which runs
  // after ours, would close it again. A tap that opened the tip keeps ignoring them until the next pointer down.
  const touch = React.useRef(false);
  const triggerEl = React.useRef<HTMLButtonElement>(null);

  // A touch that started on the trigger but never became a click (dragged away) must not keep the tip open:
  // any pointer down outside the trigger clears the flag, so Radix can close it.
  React.useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => {
      if (!(e.target instanceof Node && triggerEl.current?.contains(e.target)))
        touch.current = false;
    };
    document.addEventListener('pointerdown', outside, true);
    return () => {
      document.removeEventListener('pointerdown', outside, true);
    };
  }, [open]);

  const locked =
    React.isValidElement<{ disabled?: boolean }>(children) && children.props.disabled === true;
  const trigger = wrap ? (
    <span
      tabIndex={0}
      // a Tab stop around a locked control needs a role and a name (R2-D6): the tip says why it is locked
      {...(locked ? { role: 'group', 'aria-label': text } : {})}
      className={cn('inline-flex rounded-md [&>*]:pointer-events-none', className)}
    >
      {children}
    </span>
  ) : (
    children
  );

  if (text === '') return children;

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip
        open={open}
        onOpenChange={(next) => {
          if (touch.current) return;
          setOpen(next);
        }}
      >
        <TooltipTrigger
          asChild
          ref={triggerEl}
          onPointerDown={(e) => {
            touch.current = e.pointerType === 'touch';
          }}
          onPointerCancel={() => {
            touch.current = false; // the touch became a scroll: no click will come
          }}
          onClick={(e) => {
            if (!touch.current) return;
            const show = !open && !onControl(e.target);
            setOpen(show);
            if (!show) touch.current = false;
          }}
        >
          {trigger}
        </TooltipTrigger>
        <TooltipContent
          side={side}
          sideOffset={6}
          collisionPadding={8}
          className={cn(LOOK, 'bg-foreground text-background')}
          onEscapeKeyDown={() => {
            touch.current = false;
          }}
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
