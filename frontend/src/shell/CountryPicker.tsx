import { useEffect, useRef, useState } from 'react';
import { useInfo } from './info';
import { PENDING_COUNTRY_RULES, type CountryRule } from './pending';

function Flag({ id }: { id: string }) {
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

/** Which country's building rules the header shows. Choosing one changes the shown name only: the rules are
 * neither sent nor applied yet (CHANGE 11:05). */
export function CountryPicker() {
  const { info } = useInfo();
  const rules =
    (info as { country_rules?: CountryRule[] } | null)?.country_rules ?? PENDING_COUNTRY_RULES;
  const [chosenId, setChosenId] = useState<string | null>(null);
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

  const chosen = rules.find((r) => r.id === chosenId) ?? rules[0];
  if (!chosen) return null;
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
        aria-label={`Country rules: ${chosen.name}`}
        data-pending="country-rules"
        onClick={() => {
          setOpen(!open);
        }}
      >
        <Flag id={chosen.id} />
        <span className="country-name">{chosen.name}</span>
        <Chevron />
      </button>
      {open && (
        <div className="country-pop" role="group" aria-label="Building rules the agent follows">
          <p className="country-pop-title">Building rules the agent follows</p>
          {rules.map((rule) => (
            <button
              key={rule.id}
              type="button"
              className="country-option v-press"
              aria-pressed={rule.id === chosen.id}
              onClick={() => {
                setChosenId(rule.id);
                setOpen(false);
              }}
            >
              <Flag id={rule.id} />
              <span className="country-option-text">
                <span className="country-option-name">{rule.name}</span>
                <span className="country-option-law">{rule.law}</span>
              </span>
              {rule.id === chosen.id && (
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
              )}
            </button>
          ))}
          <p className="country-pop-note">Rules are not applied yet.</p>
        </div>
      )}
    </div>
  );
}
