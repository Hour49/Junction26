import { useState } from 'react';
import {
  postRelevance,
  previewUrl,
  readAsPlan,
  type FileStatus,
  type RelevanceRequest,
} from '../api';
import {
  CLASS_LABEL,
  callError,
  callLine,
  canCall,
  canReadAsPlan,
  planChance,
  readError,
  readLine,
  verdictOf,
} from './triage';

const NAME_KEY = 'countersign.surveyorName'; // the surveyor's key: one typed name for every call

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}

function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, the call still works
  }
}

/** The trace's triage card (file-triage.md flow 3-6); `onFile` takes a POST's answer. */
export function TriageCard(props: {
  projectId: string;
  file: FileStatus;
  onFile: (file: FileStatus) => void;
}) {
  const { projectId, file, onFile } = props;
  const [name, setName] = useState(savedName);
  const [sending, setSending] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [noPreview, setNoPreview] = useState(false);
  const t = file.triage;
  if (!t || t.class === 'floor_plan') return null;

  const send = async (
    busy: string,
    request: () => Promise<FileStatus>,
    wording: (e: unknown) => string,
  ) => {
    setSending(busy);
    setFailed(null);
    try {
      onFile(await request());
    } catch (e) {
      setFailed(wording(e));
    } finally {
      setSending(null);
    }
  };
  const relevance = (body: RelevanceRequest) =>
    send('Saving your call…', () => postRelevance(projectId, file.id, body), callError);
  const by = () => {
    const typed = name.trim();
    saveName(typed);
    return typed;
  };
  const call = (verdict: 'related' | 'unrelated') => {
    // undo defaults to false server-side; the body is relevance_request.json as is
    void relevance({ verdict, by: by() } as RelevanceRequest);
  };
  const read = () => {
    if (!window.confirm(`Read ${file.path} as a floor plan? This can't be undone.`)) return;
    void send('Asking for the reading…', () => readAsPlan(projectId, file.id, by()), readError);
  };
  const { description: d, relevance: r } = t;
  const verdict = verdictOf(t);
  const said = callLine(t);
  const offerCall = !said && canCall(file);
  const offerRead = canReadAsPlan(file);
  const blocked = sending !== null || name.trim() === '';

  return (
    <section aria-label="Is it a floor plan?" className="v-card ingest-triage">
      {t.read_as_plan ? (
        <>
          <h2 className="v-h3">Read as a floor plan on {t.read_as_plan.by}’s call</h2>
          <p className="output">
            Triage said: {CLASS_LABEL[t.class]} ({planChance(t.p_plan)} chance of a floor plan)
          </p>
        </>
      ) : (
        <>
          <h2 className="v-h3">Not a floor plan: {CLASS_LABEL[t.class]}</h2>
          <p className="output">
            Chance of a floor plan {planChance(t.p_plan)} ({t.method})
          </p>
        </>
      )}
      {noPreview ? (
        <p>Preview not available</p>
      ) : (
        <img
          className="ingest-triage-preview"
          src={previewUrl(projectId, file.id)}
          alt={`${file.path} as uploaded`}
          onError={() => {
            setNoPreview(true);
          }}
        />
      )}
      <h3 className="ingest-triage-h">What is on it</h3>
      {d ? (
        <>
          <p>{d.text}</p>
          <p>Subject: {d.subject}</p>
          {d.text_seen.length > 0 && (
            <details>
              <summary>Text printed on it ({d.text_seen.length})</summary>
              <ul>
                {d.text_seen.map((s, i) => (
                  <li key={String(i)}>{s}</li>
                ))}
              </ul>
              {d.language && <p>language: {d.language}</p>}
            </details>
          )}
          <p className="output">Described by {d.model}</p>
        </>
      ) : (
        <p>{t.note}</p>
      )}
      <h3 className="ingest-triage-h">Does it belong to this project?</h3>
      <p>
        <span className={`v-pill${t.verdict === 'unsure' ? ' v-pill--warn' : ''}`}>
          {verdict.pill}
        </span>{' '}
        {t.verdict && verdict.sentence}
      </p>
      {r ? (
        <>
          <p>{r.why}</p>
          {r.matched_on.length > 0 && <p>Matched on: {r.matched_on.join(', ')}</p>}
          <p className="output">Judged by {r.judge}</p>
        </>
      ) : (
        d && t.note && <p>{t.note}</p>
      )}
      {said && (
        <div className="ingest-triage-call">
          <p>{said}</p>
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            disabled={sending !== null}
            onClick={() => void relevance({ undo: true })}
          >
            Undo the call
          </button>
        </div>
      )}
      {t.read_as_plan && <p>{readLine(t.read_as_plan)}</p>}
      {(offerCall || offerRead) && (
        <div className="ingest-triage-call">
          <label>
            Your name
            <input
              type="text"
              maxLength={100}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </label>
          {offerCall && (
            <>
              <button
                type="button"
                className="v-btn v-press"
                disabled={blocked}
                onClick={() => {
                  call('related');
                }}
              >
                It is related
              </button>
              <button
                type="button"
                className="v-btn v-btn--secondary v-press"
                disabled={blocked}
                onClick={() => {
                  call('unrelated');
                }}
              >
                It is not related
              </button>
            </>
          )}
          {offerRead && (
            <button
              type="button"
              className="v-btn v-btn--secondary v-press"
              disabled={blocked}
              onClick={read}
            >
              Read it as a floor plan
            </button>
          )}
          {offerCall && (
            <p className="output">
              Your call replaces the suggestion and settles this file&apos;s issue. It does not read
              the file as a plan.
            </p>
          )}
        </div>
      )}
      {sending && <p>{sending}</p>}
      {failed && (
        <p role="alert" className="ingest-error">
          {failed}
        </p>
      )}
    </section>
  );
}
