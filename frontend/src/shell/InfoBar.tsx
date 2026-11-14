import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { errorText } from '../api';
import { useInfo } from './info';
import { OFFLINE_TEXT } from './strings';

/** Under the header on every route: whether the app runs offline (ui-bugs 12: no "What runs"). */
/** `wide`: the account and workspace routes, whose header row is 1280 px (shared.md "Header"). */
export function InfoBar({ wide = false }: { wide?: boolean }) {
  const { info, error, reload } = useInfo();
  const width = wide ? ' info-bar--wide' : '';
  if (error !== null) {
    const { detail, code } = errorText(error);
    const text = `${detail} (${code})`;
    return (
      <div className={`info-bar info-bar-error${width}`} role="alert">
        <span>The server did not answer: {text}</span>
        <Button variant="secondary" size="pill-sm" onClick={reload}>
          Retry
        </Button>
      </div>
    );
  }
  if (info === null) {
    return (
      <div className={`info-bar${width}`} role="status">
        Checking the server…
      </div>
    );
  }
  // With keys there is nothing to say: no empty strip.
  if (!info.no_keys) return null;
  return (
    <div className={`info-bar${width}`}>
      <Badge variant="warn" className="px-2.5 py-[3px] text-[13px] font-semibold">
        {OFFLINE_TEXT}
      </Badge>
    </div>
  );
}
