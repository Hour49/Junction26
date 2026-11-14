import { useEffect, useRef, useState } from 'react';
import { rulePacksOf } from '../api';
import { useInfo } from './info';
import { withPack } from './route';

/** By ISO country code ("FI"); none for others. */
function Flag({ country }: { country: string }) {
  const id = country.toLowerCase();
  if (id === 'fi')
    return (
      <svg className="flag" width="26" height="18" viewBox="0 0 18 11" aria-hidden="true">
        <rect width="18" height="11" fill="#ffffff" stroke="#d2d2d7" strokeWidth="0.5" />
        <rect x="5" width="3" height="11" fill="#002f6c" />
        <rect y="4" width="18" height="3" fill="#002f6c" />
      </svg>
    );
  if (id === 'ch')
    return (
      <svg
        className="flag flag--square"
        width="18"
        height="18"
        viewBox="0 0 32 32"
        aria-hidden="true"
      >
        <rect width="32" height="32" fill="#da291c" />
        <rect x="13" y="6" width="6" height="20" fill="#ffffff" />
        <rect x="6" y="13" width="20" height="6" fill="#ffffff" />
      </svg>
    );
  return null;
}

const Chevron = () => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M6 9l6 6 6-6" />
  </svg>
);

const Check = () => (
  <svg
    className="country-check"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);

/** The building-rule pack the project screens pre-check against (#139, shared.md "Country picker"). The choice lives
 * in the URL (`?pack=`): choosing writes it, nothing is stored or sent. Only on project routes, only with packs. */
export function CountryPicker({ pack }: { pack: string | null }) {
  const { info } = useInfo();
  const packs = rulePacksOf(info);
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', outside);
    return () => {
      document.removeEventListener('mousedown', outside);
    };
  }, [open]);

  if (packs.length === 0) return null;
  const chosen = packs.find((p) => p.id === pack) ?? null;
  const choose = (id: string | null) => {
    setOpen(false);
    window.location.hash = withPack(window.location.hash || '#/', id);
  };
  return (
    <div
      className="country"
      ref={wrap}
      onKeyDown={(event) => {
        if (event.key !== 'Escape' || !open) return;
        setOpen(false);
        button.current?.focus();
      }}
    >
      <button
        ref={button}
        type="button"
        className="header-pill country-button v-press"
        aria-expanded={open}
        aria-label={`Country rules: ${chosen ? chosen.country_name : 'none'}`}
        onClick={() => {
          setOpen(!open);
        }}
      >
        {chosen && <Flag country={chosen.country} />}
        <span className="country-name">{chosen ? chosen.country_name : 'No checks'}</span>
        <Chevron />
      </button>
      {open && (
        <div className="country-pop" role="group" aria-label="Building rules the agent follows">
          <p className="country-pop-title">Building rules the agent follows</p>
          <button
            type="button"
            className="country-option v-press"
            aria-pressed={chosen === null}
            onClick={() => {
              choose(null);
            }}
          >
            <span className="country-option-text">
              <span className="country-option-name">No checks</span>
            </span>
            {chosen === null && <Check />}
          </button>
          {packs.map((p) => (
            <button
              key={p.id}
              type="button"
              className="country-option v-press"
              aria-pressed={p.id === chosen?.id}
              onClick={() => {
                choose(p.id);
              }}
            >
              <Flag country={p.country} />
              <span className="country-option-text">
                <span className="country-option-name">{p.country_name}</span>
                <span className="country-option-law">{`${p.name} · ${p.version}`}</span>
              </span>
              {p.id === chosen?.id && <Check />}
            </button>
          ))}
          {/* The pack's note, verbatim (#142): a pre-check, not a certificate. */}
          <p className="country-pop-note">
            {chosen ? chosen.note : 'Choose a country to pre-check its building rules.'}
          </p>
        </div>
      )}
    </div>
  );
}
