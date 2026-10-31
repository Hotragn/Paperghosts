import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import Method from './Method.tsx'

type Field = {
  value: string
  quote: string
  verified: boolean
  in_text: [number, number] | null
  in_headline: [number, number] | null
}

type Report = {
  article_id: string
  paper: string
  date: string
  headline: string
  text: string
  place: Field | null
  place_state: Field | null
  seen: Field | null
  outcome: Field | null
  specific_place: Field | null
  place_type: Field | null
  precision: Field | null
  people: Field[]
  printed_in: { lccn: string; place: string | null; state: string | null; from: string }
  headline_legible: number
  text_legible: number
  like?: { article_id: string; score: number }[]
  clippings: { src: string; loc: string | null }[]
  issue_page: string | null
}

// the index card's rows, in the order a reader asks for them
const ROWS: [keyof Report, string][] = [
  ['place', 'Place'],
  ['place_state', 'State'],
  ['seen', 'What was seen'],
  ['outcome', 'Outcome'],
  ['specific_place', 'Building or spot'],
  ['place_type', 'Kind of place'],
  ['precision', 'Precision'],
]
const OUTCOMES = ['unknown', 'unexplained', 'explained', 'hoax']
const STAMPS: Record<string, string> = {
  unknown: 'Outcome unknown',
  unexplained: 'Unexplained',
  explained: 'Explained',
  hoax: 'Hoax',
}

const year = (r: Report) => r.date.slice(0, 4)
const decade = (r: Report) => `${r.date.slice(0, 3)}0s`
const printedIn = (r: Report) => [r.printed_in.place, r.printed_in.state].filter(Boolean).join(', ')
// a headline the OCR garbled gets a plain title; its raw text still shows beneath
const garbled = (r: Report) => r.headline_legible < 0.5
const span = (rs: Report[]) => {
  const years = rs.map(year).sort()
  return `${years[0]}–${years[years.length - 1]}`
}
const paperName = (paper: string) => paper.replace(/\s*\[volume\]/i, '').replace(/\s+\d{4}-(\d{4})?$/, '')

function fieldsOf(r: Report): [string, Field][] {
  const named = ROWS.flatMap(([key, label]) => {
    const f = r[key] as Field | null
    return f ? [[label, f] as [string, Field]] : []
  })
  return [...named, ...r.people.map((p): [string, Field] => ['Person', p])]
}

// the text with each quoted span marked; spans that share a range share one mark
function marked(text: string, fields: [string, Field][], key: 'in_text' | 'in_headline'): ReactNode[] {
  const spans: { start: number; end: number; labels: string[] }[] = []
  for (const [label, f] of fields) {
    const at = f[key]
    if (!at) continue
    const same = spans.find((s) => s.start === at[0] && s.end === at[1])
    if (same) {
      if (!same.labels.includes(label)) same.labels.push(label)
    } else spans.push({ start: at[0], end: at[1], labels: [label] })
  }
  spans.sort((a, b) => a.start - b.start)
  const out: ReactNode[] = []
  let at = 0
  for (const s of spans) {
    if (s.start < at) continue
    if (s.start > at) out.push(text.slice(at, s.start))
    const labels = s.labels.join(', ').toLowerCase()
    out.push(
      <mark key={s.start} title={labels}>
        {text.slice(s.start, s.end)}
        <span className="sr-only"> ({labels})</span>
      </mark>,
    )
    at = s.end
  }
  out.push(text.slice(at))
  return out
}

function Stamp({ outcome }: { outcome: Field | null }) {
  const value = outcome?.value ?? 'unknown'
  return <span className={`stamp stamp-${value}`}>{STAMPS[value] ?? value}</span>
}

function Value({ field }: { field: Field | null }) {
  if (!field) return <span className="not-stated">Not stated</span>
  return (
    <>
      <span className="value">{field.value.replaceAll('_', ' ')}</span>
      <q className="quote">{field.quote}</q>
      <span className={field.verified ? 'check' : 'check unverified'}>
        {field.verified ? 'Quote verified in the scan’s text' : 'Quote not found in the text'}
      </span>
    </>
  )
}

function Case({ r, byId }: { r: Report; byId: Map<string, Report> }) {
  const fields = fieldsOf(r)
  const lines = r.headline.split(/\n+/).map((l) => l.trim()).filter(Boolean)
  return (
    <div className="case">
      <div className="case-grid">
        <figure className="clipping">
          {r.clippings.map((c, i) => (
            <img
              key={c.src}
              src={c.src}
              loading="lazy"
              alt={`The scanned clipping${r.clippings.length > 1 ? `, part ${i + 1} of ${r.clippings.length}` : ''}. Its transcription is beside it.`}
            />
          ))}
          <figcaption>Scanned by the Library of Congress, Chronicling America</figcaption>
        </figure>
        <div className="transcription">
          <h3 className="deck">
            {lines.map((line, i) => (
              <span key={i} className={i === 0 ? 'deck-top' : 'deck-line'}>
                {line}
              </span>
            ))}
          </h3>
          <p className="ocr">{marked(r.text, fields, 'in_text')}</p>
          <p className="note">The text is the scan’s OCR as printed, errors and all. Marked words are the quotes the label rests on.</p>
        </div>
      </div>
      <dl className="index-card">
        {ROWS.map(([key, label]) => (
          <div key={key} className="row">
            <dt>{label}</dt>
            <dd>
              <Value field={r[key] as Field | null} />
            </dd>
          </div>
        ))}
        <div className="row">
          <dt>Printed in</dt>
          <dd>
            <span className="value">{printedIn(r) || 'Not recorded'}</span>
            <span className="check">The paper’s place, from its {r.printed_in.from} (LCCN {r.printed_in.lccn}), not the story’s</span>
          </dd>
        </div>
        <div className="row">
          <dt>People</dt>
          <dd>
            {r.people.length === 0 ? (
              <span className="not-stated">Not stated</span>
            ) : (
              <ul>
                {r.people.map((p, i) => (
                  <li key={i}>
                    <Value field={p} />
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
      <p className="sources">
        {r.issue_page && (
          <a href={r.issue_page} rel="noreferrer">
            The issue at the Library of Congress
          </a>
        )}
        {r.clippings
          .filter((c) => c.loc)
          .map((c, i) => (
            <a key={c.src} href={c.loc ?? undefined} rel="noreferrer">
              Clipping {r.clippings.length > 1 ? i + 1 : ''} at full size
            </a>
          ))}
        <span className="filing">Filed as {r.article_id.replace(/\.json$/, '')}</span>
      </p>
      {r.like && r.like.length > 0 && (
        <nav className="like" aria-label="Ghosts like this one">
          <h4>Ghosts like this one</h4>
          <ul>
            {r.like.map((l) => {
              const o = byId.get(l.article_id)
              return o ? (
                <li key={l.article_id}>
                  <a href={`#/report/${encodeURIComponent(l.article_id)}`}>{titleOf(o)}</a>
                  <span className="label"> {o.date}</span>
                </li>
              ) : null
            })}
          </ul>
          <p className="note">Ranked by Atlas Search’s moreLikeThis on the headline and text.</p>
        </nav>
      )}
      <p className="thirty" aria-label="End of the report">
        -30-
      </p>
    </div>
  )
}

function titleOf(r: Report) {
  return garbled(r)
    ? `${r.place?.value || printedIn(r) || 'A paper'}: a ghost report`
    : r.headline.split(/\n+/).map((l) => l.trim())[0]
}

function Envelope({ r, byId, opened }: { r: Report; byId: Map<string, Report>; opened: boolean }) {
  const state = r.place_state?.value
  // a place the paper wrote with its state ("Davenport, Iowa") doesn't take the state again
  const where = [r.place?.value, state && !r.place?.value.includes(state) ? state : null].filter(Boolean).join(', ')
  const first = titleOf(r)
  const ref = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    if (opened && ref.current) {
      ref.current.open = true
      ref.current.scrollIntoView({ block: 'start' })
    }
  }, [opened])
  return (
    <li>
      <details className="envelope" ref={ref} id={`report-${r.article_id}`}>
        <summary>
          <span className="label">
            <span className="date">{r.date}</span>
            <span className="paper">{paperName(r.paper)}</span>
            <span className="printed">Printed in {printedIn(r) || `LCCN ${r.printed_in.lccn}`}</span>
          </span>
          <span className="headline">{first}</span>
          {garbled(r) && r.headline && <span className="raw-headline">Headline as scanned: {r.headline.slice(0, 80)}</span>}
          <span className="where">{where ? `Story place: ${where}` : 'Story place not stated'}</span>
          <Stamp outcome={r.outcome} />
        </summary>
        <Case r={r} byId={byId} />
      </details>
    </li>
  )
}

// one clipping for each outcome: the most legible report whose sight and outcome both have verified
// quotes, captioned with those quotes and nothing else
function Samples({ reports }: { reports: Report[] }) {
  const picked = OUTCOMES.flatMap((o) => {
    const best = reports
      .filter((r) => r.outcome?.value === o && r.seen?.verified && r.outcome?.verified && r.clippings.length)
      .sort((a, b) => b.text_legible - a.text_legible)[0]
    return best ? [best] : []
  })
  return (
    <article className="samples">
      <h2 className="page-title">Paper samples</h2>
      <p className="lede">One clipping for each way a report can end, chosen as the clearest scan of its kind. Each caption is the paper’s own words.</p>
      {picked.map((r) => (
        <figure key={r.article_id} className="sample">
          {r.clippings.slice(0, 3).map((c, i) => (
            <img key={c.src} src={c.src} alt={i === 0 ? `The scanned clipping. ${r.seen?.quote ?? ''}` : ''} loading="lazy" />
          ))}
          <figcaption>
            <Stamp outcome={r.outcome} />
            <q className="quote">{r.seen?.quote}</q>
            <q className="quote">{r.outcome?.quote}</q>
            <span className="label">
              {r.date} · {paperName(r.paper)}
            </span>
            <a href={`#/report/${encodeURIComponent(r.article_id)}`}>Read the report</a>
          </figcaption>
        </figure>
      ))}
      <p className="thirty">-30-</p>
    </article>
  )
}

function useLights(): ['on' | 'off', () => void] {
  const [lights, setLights] = useState<'on' | 'off'>(() => {
    try {
      const kept = localStorage.getItem('lights')
      if (kept === 'on' || kept === 'off') return kept
    } catch {
      // storage can be blocked; the device's setting decides then
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'off' : 'on'
  })
  useEffect(() => {
    document.documentElement.dataset.lights = lights
    try {
      localStorage.setItem('lights', lights)
    } catch {
      // nothing to keep
    }
  }, [lights])
  return [lights, () => setLights((l) => (l === 'on' ? 'off' : 'on'))]
}

// the reading lamp follows the pointer and keyboard focus; with reduced motion it stays put
function useLamp() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const root = document.documentElement
    let frame = 0
    const move = (x: number, y: number) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        root.style.setProperty('--lamp-x', `${x}px`)
        root.style.setProperty('--lamp-y', `${y}px`)
      })
    }
    const onPointer = (e: PointerEvent) => move(e.clientX, e.clientY)
    const onFocus = (e: FocusEvent) => {
      const box = (e.target as Element).getBoundingClientRect?.()
      if (box) move(box.left + box.width / 2, box.top + box.height / 2)
    }
    window.addEventListener('pointermove', onPointer, { passive: true })
    window.addEventListener('focusin', onFocus)
    return () => {
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('focusin', onFocus)
    }
  }, [])
}

function App() {
  const [reports, setReports] = useState<Report[]>()
  const [error, setError] = useState<string>()
  const [query, setQuery] = useState('')
  const [era, setEra] = useState('')
  const [outcome, setOutcome] = useState('')
  const [printed, setPrinted] = useState('')
  const [lights, toggle] = useLights()
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const onHash = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const page = hash.startsWith('#/how') ? 'how' : hash.startsWith('#/samples') ? 'samples' : 'drawer'
  const openId = hash.startsWith('#/report/') ? decodeURIComponent(hash.slice(9)) : ''
  const byId = useMemo(() => new Map((reports ?? []).map((r) => [r.article_id, r])), [reports])
  useLamp()

  useEffect(() => {
    fetch('reports.json')
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then(setReports, (failure: Error) => setError(failure.message))
  }, [])

  const printedStates = useMemo(
    () => [...new Set((reports ?? []).map((r) => r.printed_in.state).filter((s): s is string => !!s))].sort(),
    [reports],
  )
  const decades = useMemo(() => [...new Set((reports ?? []).map(decade))].sort(), [reports])
  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean)
    return (reports ?? []).filter((r) => {
      if (openId) return true
      if (era && decade(r) !== era) return false
      if (outcome && (r.outcome?.value ?? 'unknown') !== outcome) return false
      if (printed && r.printed_in.state !== printed) return false
      const hay = [r.place?.value, r.place_state?.value, r.specific_place?.value, printedIn(r), r.headline, r.text, r.paper]
        .join(' ')
        .toLowerCase()
      return words.every((w) => hay.includes(w))
    })
  }, [reports, query, era, outcome, printed, openId])

  return (
    <>
      <a className="skip" href="#main">
        Skip to the content
      </a>
      <header className="masthead">
        <button type="button" className="chain" onClick={toggle} aria-pressed={lights === 'on'}>
          <span className="chain-pull" aria-hidden="true" />
          {lights === 'on' ? 'Lights off' : 'Lights on'}
        </button>
        <p className="ear">
          {reports ? `${reports.length} reports on file, ${span(reports)}` : 'The morgue'}
        </p>
        <img className="mark" src="brand/logo.svg" alt="" width="72" height="72" />
        <h1 className="nameplate">Paper Ghosts</h1>
        <nav className="rooms" aria-label="The Morgue’s rooms">
          <a href="#/" aria-current={page === 'drawer' ? 'page' : undefined}>The drawer</a>
          <a href="#/samples" aria-current={page === 'samples' ? 'page' : undefined}>Paper samples</a>
          <a href="#/how" aria-current={page === 'how' ? 'page' : undefined}>How we know</a>
        </nav>
        <p className="tagline">A morgue of ghost reports from American newspapers, each one filed with the words it rests on.</p>
      </header>

      <main id="main">
        {page === 'how' && <Method />}
        {page === 'samples' && reports && <Samples reports={reports} />}
        {page === 'drawer' && (<>
        <form className="slip" role="search" onSubmit={(e) => e.preventDefault()}>
          <p className="slip-head">Request slip</p>
          <label>
            Town, state or word
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Georgetown, Ohio, knocking…" />
          </label>
          <label>
            Decade
            <select value={era} onChange={(e) => setEra(e.target.value)}>
              <option value="">Any</option>
              {decades.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
          <label>
            Outcome
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="">Any</option>
              {OUTCOMES.map((o) => (
                <option key={o} value={o}>
                  {STAMPS[o]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Printed in
            <select value={printed} onChange={(e) => setPrinted(e.target.value)}>
              <option value="">Any state</option>
              {printedStates.map((st) => (
                <option key={st}>{st}</option>
              ))}
            </select>
          </label>
        </form>

        <section id="drawer" aria-live="polite" aria-busy={!reports && !error}>
          {error && <p className="count">The drawer could not be opened ({error}).</p>}
          {!reports && !error && <p className="count">Opening the drawer…</p>}
          {reports && (
            <p className="count">
              {shown.length === 0
                ? 'Nothing filed under that.'
                : `${shown.length} report${shown.length === 1 ? '' : 's'}, ${span(shown)}. Clearest scans first.`}
            </p>
          )}
          <ol className="envelopes">
            {shown.map((r) => (
              <Envelope key={r.article_id} r={r} byId={byId} opened={r.article_id === openId} />
            ))}
          </ol>
        </section>
        </>)}
      </main>

      <footer className="colophon">
        <h2>How this was made</h2>
        <p>
          These are the reports among 450 articles drawn from the archive and labelled one at a time under the project’s
          labelling policy (POLICY.md) by an AI labeller, Claude, working article by article in a labelling page. A blind second pass relabelled every gold
          article and a seeded fifth of the rest, and fresh judges ruled every disagreement blind. Each value carries the
          exact words of the scan that state it, and a quote verifier checks that those words are in the text.
        </p>
        <p>
          The automatic reader that will label the rest of the archive is still being trained, on labels from an open-weight model run
          locally. Nothing on this page was written by it.
        </p>
        <p>
          Text: the AmericanStories dataset’s OCR of Chronicling America. Scans: the Library of Congress, Chronicling
          America.
        </p>
      </footer>
    </>
  )
}

export default App
