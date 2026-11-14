import type { Proof } from '../api';

// Inline so the tests can see them: a wide table scrolls in its wrapper and never breaks inside a word
// (the page itself wraps long paths with overflow-wrap: anywhere).
const WRAP = { overflowX: 'auto' } as const;
const CELLS = { overflowWrap: 'normal', wordBreak: 'normal' } as const;

/** The proof of a building-model answer (no page to draw on): the objects counted and the storeys. */
export function ModelProof({ proof }: { proof: Proof }) {
  const storeys = proof.storeys ?? [];
  const classes = [...new Set(storeys.flatMap((s) => Object.keys(s.counts)))];
  return (
    <div className="en-model">
      <p className="en-small">Building model: no sheet to draw on.</p>
      {proof.objects && (
        <div className="en-tablewrap" style={WRAP}>
          <table style={CELLS}>
            <caption>Model objects</caption>
            <thead>
              <tr>
                <th>Name</th>
                <th>Class</th>
                <th>Storey</th>
                <th>GlobalId</th>
              </tr>
            </thead>
            <tbody>
              {proof.objects.map((o) => (
                <tr key={o.id}>
                  <td>{o.name ?? '–'}</td>
                  <td>{o.class}</td>
                  <td>{o.storey ?? '–'}</td>
                  <td className="en-mono">{o.global_id ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {storeys.length > 0 && (
        <div className="en-tablewrap" style={WRAP}>
          <table style={CELLS}>
            <caption>Objects per storey</caption>
            <thead>
              <tr>
                <th>Storey</th>
                {classes.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {storeys.map((s) => (
                <tr key={s.storey}>
                  <th scope="row">{s.storey}</th>
                  {classes.map((c) => (
                    <td key={c}>{s.counts[c] ?? 0}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
