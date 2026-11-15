import type { ReactElement } from 'react';
import { Tip } from '@/components/ui/tip';

/**
 * The shared Tip on a button that may be disabled. A disabled button gets no hover or focus, so the tip sits on a
 * span that is always there (the button is never remounted when it locks or unlocks); the span takes focus only
 * while the button is disabled, and lets hover through to it while it is enabled.
 */
export function LockTip({
  text,
  locked,
  children,
}: {
  text: string;
  locked: boolean;
  children: ReactElement;
}) {
  return (
    <Tip text={text}>
      <span
        tabIndex={locked ? 0 : -1}
        className="inline-flex rounded-md [&>:disabled]:pointer-events-none"
      >
        {children}
      </span>
    </Tip>
  );
}
