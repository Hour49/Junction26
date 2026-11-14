import { rulePacksOf } from '../api';
import { useInfo } from '../shell/info';
import type { AiFinding, Finding, LawChange, LawCheck } from './agent';

type Tone = 'fail' | 'unclear' | 'pass';
const ICON: Record<Tone, string> = { fail: '✕', unclear: '!', pass: '✓' };

/** LC-12's status words; icon and word, colour never alone. */
const CHANGE: Record<LawChange, { word: string; tone: Tone }> = {
  newly_fails: { word: 'Would not meet', tone: 'fail' },
  still_fails: { word: "Still doesn't meet", tone: 'fail' },
  newly_cannot_tell: { word: "Can't tell", tone: 'unclear' },
  now_passes: { word: 'Meets now', tone: 'pass' },
  still_passes: { word: 'Meets', tone: 'pass' }, // a rule the change touches that it still meets
};
const ORDER: LawChange[] = [
  'newly_fails',
  'still_fails',
  'newly_cannot_tell',
  'now_passes',
  'still_passes',
];

const VERDICT: Record<AiFinding['verdict'], { word: string; tone: Tone }> = {
  would_not_meet: { word: 'Would not meet', tone: 'fail' },
  check: { word: "Can't tell", tone: 'unclear' },
  meets: { word: 'Meets', tone: 'pass' },
};

const COMPARE: Record<string, string> = {
  '>=': 'at least',
  '>': 'more than',
  '<=': 'at most',
  '<': 'less than',
  '=': 'exactly',
};

const unitOf = (u: string | null) => (u === 'm2' ? 'm²' : u === 'count' ? '' : (u ?? ''));
const num = (v: number | null) => (v === null ? 'not known' : String(Math.round(v * 100) / 100));
const withUnit = (v: number | null, u: string | null) =>
  v === null ? num(v) : `${num(v)} ${unitOf(u)}`.trim();

function Status({ word, tone }: { word: string; tone: Tone }) {
  return (
    <span className={`ag-law-status ag-law-status--${tone}`}>
      <span aria-hidden="true">{ICON[tone]}</span> {word}
    </span>
  );
}

/** The clause ref as a link (new tab), or plain text without a url. */
function Ref({ text, url }: { text: string; url: string | null }) {
  return url ? (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {text}
    </a>
  ) : (
    <span>{text}</span>
  );
}

function Quote(props: { quote: string | null; quoteEn?: string | null; open: boolean }) {
  if (!props.quote && !props.quoteEn) return null;
  return (
    <details className="ag-law-quote" open={props.open}>
      <summary>The clause</summary>
      {props.quote && <blockquote>{props.quote}</blockquote>}
      {props.quoteEn && (
        <>
          <p>{props.quoteEn}</p>
          <p className="en-small">Translation ours, unofficial</p>
        </>
      )}
    </details>
  );
}

/** The subject: a button that shows its room on the card's plan (LC-15). */
type OnPick = (subject: string, ev?: string | null, ref?: string | null) => void;

function Subject(props: {
  name: string;
  ev?: string | null;
  subjectRef?: string | null;
  onPick?: OnPick;
}) {
  const { name, ev, subjectRef, onPick } = props;
  return onPick ? (
    <button
      type="button"
      className="ag-law-subject"
      onClick={() => {
        onPick(name, ev, subjectRef);
      }}
    >
      {name}
    </button>
  ) : (
    <span>{name}</span>
  );
}

function FindingRow({ f, onPick }: { f: Finding; onPick?: OnPick }) {
  const c = CHANGE[f.change];
  return (
    <li className="ag-law-row">
      <p className="ag-law-head">
        <Status word={c.word} tone={c.tone} /> <span className="ag-law-title">{f.title}</span>
      </p>
      <p className="ag-law-values">
        <Subject name={f.subject} ev={f.ev} subjectRef={f.subject_ref} onPick={onPick} />:{' '}
        {withUnit(f.before.value, f.unit)} → {withUnit(f.after.value, f.unit)}
        <span className="ag-law-limit">
          {' '}
          · {f.comparison_text} {withUnit(f.limit, f.unit)}
        </span>
      </p>
      {f.after.why && <p className="en-small">{f.after.why}</p>}
      <p className="ag-law-clause">
        <Ref text={f.clause.ref} url={f.clause.url} />
      </p>
      <Quote quote={f.clause.quote} quoteEn={f.clause.quote_en} open={f.change === 'newly_fails'} />
    </li>
  );
}

function AiRow({ a, onPick }: { a: AiFinding; onPick?: OnPick }) {
  const v = VERDICT[a.verdict];
  return (
    <li className="ag-law-row">
      <p className="ag-law-head">
        <Status word={v.word} tone={v.tone} />{' '}
        <span className="ag-law-title">
          <Ref text={`${a.ref} · ${a.law}`} url={a.url} />
        </span>
      </p>
      <p className="ag-law-values">
        <Subject name={a.subject} onPick={onPick} />: {withUnit(a.value ?? null, a.unit)}
        <span className="ag-law-limit">
          {' '}
          · {COMPARE[a.comparison] ?? a.comparison} {withUnit(a.limit, a.unit)}
        </span>
      </p>
      <Quote quote={a.quote} quoteEn={a.quote_en} open={false} />
    </li>
  );
}

// shortcut: opens the header's picker by clicking its button (it exposes no opener); ask the shell for one if the
// header's markup changes.
function openPicker() {
  document.querySelector<HTMLButtonElement>('.country-button')?.click();
}

/** The edit card's "Building rules" (plan-edit-law-check.md LC-12 to LC-14): the rule-pack findings, the AI's
 * checked reading of the law, other clauses to read, the note; without a country, how to pick one. */
export function LawSection(props: { law: LawCheck | null | undefined; onPick?: OnPick }) {
  const { law, onPick } = props;
  const packs = rulePacksOf(useInfo().info);
  if (!law) {
    return (
      <section className="ag-law" aria-label="Building rules">
        <h4 className="en-label">Building rules</h4>
        <p className="en-small">Pick a country to check this change against its building rules</p>
        {packs.length > 0 && (
          <button type="button" className="en-chip v-press ag-law-pick" onClick={openPicker}>
            Pick a country
          </button>
        )}
      </section>
    );
  }
  const country = packs.find((p) => p.id === law.pack)?.country_name ?? law.pack_name;
  const findings = [...law.findings].sort(
    (a, b) => ORDER.indexOf(a.change) - ORDER.indexOf(b.change),
  );
  // A clause already shown as a finding or an AI finding is not offered again.
  const shown = [...law.findings.map((f) => f.clause.ref), ...law.ai_findings.map((a) => a.ref)];
  const aiIds = new Set(law.ai_findings.map((a) => a.clause_id));
  const related = law.related
    .filter((r) => !aiIds.has(r.id) && !shown.some((ref) => ref.includes(r.ref)))
    .slice(0, 3);
  return (
    <section className="ag-law" aria-label={`Building rules · ${country}`}>
      <h4 className="en-label">Building rules · {country}</h4>
      {findings.length > 0 ? (
        <ul className="ag-law-rows" aria-label="Rule checks">
          {findings.map((f) => (
            <FindingRow key={`${f.rule_id}:${f.subject}`} f={f} onPick={onPick} />
          ))}
        </ul>
      ) : (
        <p className="en-small">No checked rule changes with this edit.</p>
      )}
      {law.unchanged > 0 && (
        <p className="en-small">
          {law.unchanged} other {law.unchanged === 1 ? 'check' : 'checks'} unchanged
        </p>
      )}
      {law.ai_findings.length > 0 && (
        <>
          <h5 className="ag-law-h">The AI also found in the law</h5>
          <p className="en-small">
            AI reading of the law, checked against the clause&apos;s number; not a rule check
          </p>
          <ul className="ag-law-rows" aria-label="The AI also found in the law">
            {law.ai_findings.map((a) => (
              <AiRow key={`${a.clause_id}:${a.subject}`} a={a} onPick={onPick} />
            ))}
          </ul>
        </>
      )}
      {related.length > 0 && (
        <>
          <h5 className="ag-law-h">Other rules to read</h5>
          <ul className="ag-law-related" aria-label="Other rules to read">
            {related.map((r) => (
              <li key={r.id}>
                <Ref text={`${r.ref} · ${r.law_title_en}`} url={r.url} />
                <span className="en-small"> {r.summary_en}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="en-small">{law.note}</p>
    </section>
  );
}
