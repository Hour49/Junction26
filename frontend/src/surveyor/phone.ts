import { useEffect, useState } from 'react';

/** At this width and narrower the surveyor is one column in the page's flow (surveyor.md "Phone"). */
export const ONE_COLUMN = '(max-width: 760px)';

/** Whether the window matches `query`, following resizes; false where matchMedia is missing. */
export function usePhone(query = ONE_COLUMN): boolean {
  const [phone, setPhone] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const list = window.matchMedia(query);
    const follow = () => {
      setPhone(list.matches);
    };
    follow();
    list.addEventListener('change', follow);
    return () => {
      list.removeEventListener('change', follow);
    };
  }, [query]);
  return phone;
}
