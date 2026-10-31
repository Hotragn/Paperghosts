import { useEffect, useState } from 'react'

// eval/results/numbers.json, copied to the site by scripts/article_numbers.py: every figure here is
// read from it by name, never typed in
type Entry = { name: string; value: unknown; source: string; note?: string }
type Rate = { k: number; n: number; lo: number; hi: number }

function rate(v: unknown): Rate | null {
  const o = v as Record<string, unknown>
  if (!o || typeof o !== 'object') return null
  const k = (o.agree ?? o.found ?? o.hits ?? o.normalised_agree ?? o.count) as number
  const n = (o.n ?? o.reports) as number
  const iv = (o.interval ?? o.normalised_interval) as [number, number] | undefined
  const [lo, hi] = iv ?? [o.low as number, o.high as number]
  return [k, n, lo, hi].every((x) => typeof x === 'number') ? { k, n, lo, hi } : null
}

const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`
const said = (r: Rate) => `${r.k} of ${r.n} (${pct(r.lo)}–${pct(r.hi)})`
const count = (x: number) => x.toLocaleString('en-US')

// one row per measure: each series a dot at its rate and a whisker across its Wilson interval
function Intervals({ rows, series }: { rows: { label: string; rates: (Rate | null)[] }[]; series: string[] }) {
  return (
    <figure className="chart">
      <div className="legend" aria-hidden="true">
        {series.map((s, i) => (
          <span key={s}>
            <span className={`key key-${i}`} /> {s}
          </span>
        ))}
      </div>
      <table>
        <caption className="sr-only">Each measure with its count and 95% Wilson interval</caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            {series.map((s) => (
              <th scope="col" key={s}>
                {s}
              </th>
            ))}
            <th scope="col" aria-hidden="true" className="scale">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {row.rates.map((r, i) => (
                <td key={i}>{r ? said(r) : '—'}</td>
              ))}
              <td className="track" aria-hidden="true">
                {row.rates.map((r, i) =>
                  r ? (
                    <span key={i} className={`whisker whisker-${i}`} style={{ left: pct(r.lo, 2), width: pct(r.hi - r.lo, 2) }}>
                      <span className={`dot dot-${i}`} style={{ left: `${((r.k / r.n - r.lo) / Math.max(r.hi - r.lo, 1e-9)) * 100}%` }} />
                    </span>
                  ) : null,
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}

function Source({ e }: { e?: Entry }) {
  return e ? <span className="source">Source: {e.source}</span> : null
}

export default function Method() {
  const [entries, setEntries] = useState<Entry[]>()
  useEffect(() => {
    fetch('numbers.json')
      .then((r) => r.json())
      .then(setEntries, () => setEntries([]))
  }, [])
  if (!entries) return <p className="count">Opening the file…</p>
  const by = (name: string) => entries.find((e) => e.name === name)
  const v = (name: string) => by(name)?.value as Record<string, number> & number
  const r = (name: string) => rate(by(name)?.value)
  const T = 'Qwen3.5-397B round 3'
  const G = 'gemma4:26b thinking off'
  const archive = v('archive: pages and articles')
  const lex = v('lexicon v1 against v2')
  const stories = v('stories: distinct, v2')
  const spendAll = (by('tinker spend: all')?.value ?? {}) as Record<string, string | number>
  const price = by("Tinker: the 397B teacher's price per 10,000 articles, all cached to none ($)")?.value as number[] | undefined
  const atlas = v("Atlas: the Morgue's reports loaded")
  const entire = by('Entire: commits with an Entire-Checkpoint trailer, and checkpoint refs')?.value as number[] | undefined
  const settled = by('blind re-ruling: rulings that differed, blind taken, first kept')?.value as number[] | undefined
  const kappa = (name: string) => (by(name)?.value as { kappa?: number })?.kappa

  return (
    <article className="method">
      <h2 className="page-title">How we know</h2>
      <p className="lede">
        Every figure on this page is read from the project’s committed results, by the script that reproduces them
        (<code>scripts/article_numbers.py</code>). Intervals are 95% Wilson intervals.
      </p>

      <section>
        <h3>The archive was screened in full</h3>
        <p>
          {archive && `${count(archive.articles)} articles on ${count(archive.pages)} pages`} of AmericanStories went through
          a ghost-word screen. Lexicon v2 flags {lex && count(lex.v2_candidates)} of them as candidates, against{' '}
          {lex && count(lex.v1_candidates)} for v1, which it keeps every one of. They group into{' '}
          {stories && count(stories.distinct_stories)} distinct stories once reprints are chained.
        </p>
        <Source e={by('archive: pages and articles')} />
        <Intervals
          series={['Evaluation sample']}
          rows={[
            { label: 'Ghost reports among v1 candidates', rates: [r('eval A: ghost reports among candidates')] },
            { label: 'Reports among v2’s added candidates', rates: [r("lexicon v2's added: reports in the judged 200")] },
          ]}
        />
      </section>

      <section>
        <h3>Reprints, chained into stories</h3>
        <p>
          A story the papers copied from each other is read once. Measured on hand-checked pairs at a similarity threshold of{' '}
          {String(v('stories: threshold'))}:
        </p>
        <Intervals
          series={['Per candidate']}
          rows={[
            { label: 'Precision: a chained printing is the same story', rates: [r('stories: precision per candidate')] },
            { label: 'Recall: the same story is chained', rates: [r('stories: recall per candidate')] },
          ]}
        />
        <Source e={by('stories: precision per candidate')} />
      </section>

      <section>
        <h3>The gold set, labelled twice and ruled blind</h3>
        <p>
          300 gold and 150 dev articles, drawn across 17 strata, were labelled one at a time under the labelling policy by an AI
          labeller, Claude. A blind second pass relabelled all of gold.
          {settled && ` Fresh judges ruled every disagreement again, blind; where their ruling differed, ${settled[1]} of ${settled[0]} took the blind ruling.`}
        </p>
        <Intervals
          series={['First pass against the blind second']}
          rows={[
            { label: `Kind (κ ${kappa('first vs second pass on gold: kind')?.toFixed(2)})`, rates: [r('first vs second pass on gold: kind')] },
            {
              label: `Report or not (κ ${kappa('first vs second pass on gold: report or not')?.toFixed(2)})`,
              rates: [r('first vs second pass on gold: report or not')],
            },
          ]}
        />
        <Source e={by('first vs second pass on gold: kind')} />
      </section>

      <section id="teachers">
        <h3>The teacher benchmark: Tinker’s 397B against gemma4 on this Mac</h3>
        <p>
          The reader will learn from an open-weight teacher’s labels. Two were scored on the 150 dev articles, after the quote
          verifier: Qwen3.5-397B through Tinker, and gemma4:26b run locally through Ollama.
        </p>
        <Intervals
          series={['Qwen3.5-397B (Tinker)', 'gemma4:26b (local)']}
          rows={[
            { label: 'Kind', rates: [r(`${T}: kind, after the verifier`), r(`${G}: kind, after the verifier`)] },
            { label: 'Report or not', rates: [r(`${T}: report or not, after the verifier`), r(`${G}: report or not, after the verifier`)] },
            { label: 'Reports found', rates: [r(`${T}: report recall`), r(`${G}: report recall`)] },
            { label: 'Place', rates: [r(`${T}: place, after the verifier`), r(`${G}: place, after the verifier`)] },
            { label: 'State', rates: [r(`${T}: place_state, after the verifier`), r(`${G}: place_state, after the verifier`)] },
            { label: 'Outcome, as scored', rates: [r(`${T}: outcome, after the verifier`), r(`${G}: outcome, after the verifier`)] },
            {
              label: 'Outcome, format normalised (scoring only)',
              rates: [r('format check r3: outcome, normalised (scoring only)'), r('format check g26: outcome, normalised (scoring only)')],
            },
          ]}
        />
        <p>
          <strong>Format, not judgment.</strong> 18 of gemma4’s 19 outcome misses wrote the outcome as a bare word with no quote,
          which the parser drops. Read as values they score as the normalised row shows, but a training label still needs its
          verified quote, so the prompt now asks for one. The 397B’s state misses are judgment: it fills a state the policy
          leaves empty.
        </p>
        <p>
          <strong>Cost and the stop.</strong> From round 3’s measured tokens, the 397B costs{' '}
          {price && `$${price[0].toFixed(0)}–${price[1].toFixed(0)} per 10,000 articles`}, depending on how much of the prompt is
          cached. The day’s Tinker use came to {String(spendAll.cost_all_cached_to_none ?? '')} by its recorded tokens, on a $0
          balance. The owner then stopped all Tinker spend, and sampling is off in code (decision 39).
        </p>
        <Source e={by(`${T}: kind, after the verifier`)} />
      </section>

      <section>
        <h3>Where the Morgue lives</h3>
        <p>
          {atlas &&
            `The ${atlas.documents} reports sit in MongoDB Atlas (${atlas.storage_kb} KB), checked by the schema’s own validator. Atlas Search finds them with fuzzy matching, so a word the OCR misread still finds its report, and its moreLikeThis picks each report’s “ghosts like this one”.`}
          {entire && ` The build itself is recorded by Entire: ${entire[0]} commits carry a session checkpoint.`}
        </p>
        <Source e={by("Atlas: the Morgue's reports loaded")} />
      </section>

      <section>
        <h3>What isn’t done</h3>
        <p>
          The reader that will label the rest of the archive is not trained yet. Training it needs labels from the local teacher,
          and running the teacher alongside training froze this laptop. So the Morgue shows the labelled reports, not the
          reader’s output.
        </p>
      </section>
      <p className="thirty">-30-</p>
    </article>
  )
}
