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

/**
 * One hover explanation for any control. Shows on hover, keyboard focus and tap; Escape closes it. Radix adds
 * `role="tooltip"` and `aria-describedby`, and moves the box away from the screen edges.
 */
export function Tip({ text, children, wrap = false, side = 'bottom', className }: TipProps) {
  const [open, setOpen] = React.useState(false);
  // On touch there is no hover: a tap toggles the tip. Radix would close it again on the same tap.
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

  const trigger = wrap ? (
    <span
      tabIndex={0}
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
          if (!next && touch.current) return;
          setOpen(next);
        }}
      >
        <TooltipTrigger
          asChild
          ref={triggerEl}
          onPointerDown={(e) => {
            touch.current = e.pointerType === 'touch';
          }}
          onClick={() => {
            if (touch.current) {
              touch.current = false;
              setOpen((o) => !o);
            }
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
