import { AnimatePresence, animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { exportText, saveBlob } from '../api'
import type { Strings } from '../i18n'
import { buildReport } from '../report'
import type { Analysis, Level, Sentence } from '../types'

const LEVEL_COLOR: Record<Level, string> = { human: '#1a7f52', mixed: '#c98a00', ai: '#d23f3f' }

interface Props {
  r: Analysis
  prev: Analysis | null
  t: Strings
  onReset: () => void
  onRescan: (text: string) => void
  rescanning: boolean
  progress: number
}

export function Results({ r, prev, t, onReset, onRescan, rescanning, progress }: Props) {
  const [focus, setFocus] = useState<number | null>(null)
  const [edits, setEdits] = useState<Record<number, string>>({})
  const usable = r.document.language?.english !== false
  const original = (i: number) => r.text.slice(r.paragraphs[i].start, r.paragraphs[i].end)
  const changed = Object.entries(edits).filter(([i, v]) => v.trim() !== original(+i).trim()).length
  const fullText = () => r.paragraphs.map((_, i) => (edits[i] ?? original(i)).trim()).filter(Boolean).join('\n\n')
  const jump = (start: number) => {
    document.getElementById(`s-${start}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setFocus(start)
    window.setTimeout(() => setFocus(null), 1800)
  }
  return (
    <div className="results">
      <Verdict r={r} prev={prev} t={t} onReset={onReset} fullText={fullText} usable={usable} />
      <motion.div className="card doc" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
        <Heatmap r={r} t={t} focus={focus} usable={usable} edits={edits}
          setEdit={(i, v) => setEdits((e) => ({ ...e, [i]: v }))} />
      </motion.div>
      <motion.aside className="side" initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.25 }}>
        {usable && <Suspects r={r} t={t} onJump={jump} />}
        {usable && <Resembles r={r} t={t} />}
        <StylePanel r={r} t={t} />
      </motion.aside>
      <AnimatePresence>
        {(changed > 0 || rescanning) && (
          <motion.div className="rescan-bar" initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}>
            {rescanning ? (
              <>
                <b>{t.rescanning}… {Math.round(progress * 100)}%</b>
                <div className="progress" style={{ flex: 1, margin: 0 }}><motion.div animate={{ width: `${Math.max(2, progress * 100)}%` }} /></div>
              </>
            ) : (
              <>
                <span>✏️ {changed} {t.changes}</span>
                <button className="btn ghost" onClick={() => setEdits({})}>↺</button>
                <button className="btn" onClick={() => onRescan(fullText())}>{t.rescan} →</button>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Counter({ value, suffix = '' }: { value: number; suffix?: string }) {
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => `${Math.round(v)}${suffix}`)
  useEffect(() => {
    const c = animate(mv, value, { duration: 1.1, ease: 'easeOut' })
    return c.stop
  }, [mv, value])
  return <motion.span>{text}</motion.span>
}

function Ring({ share, mixed }: { share: number; mixed: number }) {
  const R = 52, C = 2 * Math.PI * R
  return (
    <svg width="136" height="136" viewBox="0 0 136 136" style={{ flexShrink: 0 }}>
      <circle cx="68" cy="68" r={R} fill="none" stroke="#eef0ee" strokeWidth="14" />
      <motion.circle cx="68" cy="68" r={R} fill="none" stroke="#f0c040" strokeWidth="14" strokeLinecap="round"
        transform="rotate(-90 68 68)" strokeDasharray={C}
        initial={{ strokeDashoffset: C }} animate={{ strokeDashoffset: C * (1 - Math.min(1, share + mixed)) }}
        transition={{ duration: 1.1, ease: 'easeOut' }} />
      <motion.circle cx="68" cy="68" r={R} fill="none" stroke="#d23f3f" strokeWidth="14" strokeLinecap="round"
        transform="rotate(-90 68 68)" strokeDasharray={C}
        initial={{ strokeDashoffset: C }} animate={{ strokeDashoffset: C * (1 - share) }}
        transition={{ duration: 1.1, ease: 'easeOut' }} />
      <text x="68" y="74" textAnchor="middle" fontSize="28" fontWeight="700" fill="#111418" fontFamily="Outfit">
        {Math.round(share * 100)}%
      </text>
    </svg>
  )
}

function Verdict({ r, prev, t, onReset, fullText, usable }: {
  r: Analysis; prev: Analysis | null; t: Strings; onReset: () => void; fullText: () => string; usable: boolean
}) {
  const d = r.document
  const lo = -6, hi = 8
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100))}%`
  const oneSection = d.level === 'ai' && d.ai_share < 0.35
  const head = (
    <div className="right">
      <button className="btn ghost" onClick={onReset}>↺ {t.newCheck}</button>
      <ExportMenu r={r} t={t} fullText={fullText} />
      {r.source.name && <span className="chip">📄 {r.source.name}</span>}
    </div>
  )
  if (!usable) {
    return (
      <motion.div className="card verdict" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ fontSize: 54 }}>🌐</div>
        <div style={{ minWidth: 0 }}>
          <h2>{t.notEnglishTitle}</h2>
          <p>{t.notEnglishBody}</p>
        </div>
        {head}
      </motion.div>
    )
  }
  const pd = prev?.document
  return (
    <motion.div className="card verdict" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <div style={{ opacity: d.too_short ? 0.4 : 1 }}><Ring share={d.ai_share} mixed={d.mixed_share} /></div>
      <div style={{ minWidth: 0 }}>
        {d.too_short ? (
          <>
            <h2>{t.shortTitle}</h2>
            <p>{t.shortBody}</p>
          </>
        ) : (
          <>
            <h2 style={{ color: LEVEL_COLOR[d.level] }}>{t[`verdict_${d.level}`]}</h2>
            <p>{t[`verdictSub_${d.level}`]}</p>
          </>
        )}
        <div className="meta">
          <div className="stat"><b style={{ color: LEVEL_COLOR.ai }}><Counter value={d.ai_share * 100} suffix="%" /></b>
            <span>{t.aiFlagged} {t.ofText}{pd && <em className="delta"> ({t.before} {Math.round(pd.ai_share * 100)}%)</em>}</span></div>
          <div className="stat"><b style={{ color: LEVEL_COLOR.mixed }}><Counter value={d.mixed_share * 100} suffix="%" /></b>
            <span>{t.mixedFlagged}{pd && <em className="delta"> ({t.before} {Math.round(pd.mixed_share * 100)}%)</em>}</span></div>
          <div className="stat"><b>{d.n_words.toLocaleString()}</b><span>{t.words}</span></div>
        </div>
        <div className="scorebar" title={t.thresholdHint}>
          <div className="track">
            <div className="th" style={{ left: pos(d.thresholds.strong) }} />
            <motion.div className="mark" initial={{ left: '0%' }} animate={{ left: pos(d.score) }} transition={{ duration: 1.1, ease: 'easeOut' }} />
          </div>
          <div className="labels"><span>{t.score}: {d.score.toFixed(2)}</span><span>{t.threshold}: {d.thresholds.strong.toFixed(2)}</span></div>
        </div>
        {oneSection && !d.too_short && <div className="notice">ℹ️ {t.oneSection}</div>}
        {r.source.references_removed && <div className="notice" style={{ background: '#eef4ff', color: '#23407a' }}>📚 {t.refsRemoved}</div>}
        {r.source.ocr && <div className="notice">🔍 {t.ocrUsed}</div>}
      </div>
      {head}
    </motion.div>
  )
}

function ExportMenu({ r, t, fullText }: { r: Analysis; t: Strings; fullText: () => string }) {
  const [open, setOpen] = useState(false)
  const base = (r.source.name ?? 'metin').replace(/\.[^.]+$/, '')
  const run = async (kind: 'docx' | 'txt' | 'report') => {
    setOpen(false)
    try {
      if (kind === 'report') saveBlob(new Blob([buildReport(r, t)], { type: 'text/html' }), `${base}-rapor.html`)
      else await exportText(fullText(), kind, `${base}-duzenlenmis`)
    } catch (e) { window.alert((e as Error).message) }
  }
  return (
    <div className="menu-wrap">
      <button className="btn ghost" onClick={() => setOpen((o) => !o)}>⤓ {t.exportBtn}</button>
      <AnimatePresence>
        {open && (
          <motion.div className="menu" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            <button onClick={() => run('docx')}>📝 {t.exportDocx}</button>
            <button onClick={() => run('txt')}>📄 {t.exportTxt}</button>
            <button onClick={() => run('report')}>📊 {t.exportReport}</button>
            {r.source.name?.toLowerCase().endsWith('.docx') && <small>{t.exportNote}</small>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ---------------- heatmap ---------------- */

interface Tip { x: number; y: number; s: Sentence }

function Heatmap({ r, t, focus, usable, edits, setEdit }: {
  r: Analysis; t: Strings; focus: number | null; usable: boolean
  edits: Record<number, string>; setEdit: (i: number, v: string) => void
}) {
  const [words, setWords] = useState(false)
  const [phrases, setPhrases] = useState(true)
  const [tip, setTip] = useState<Tip | null>(null)
  const [editing, setEditing] = useState<number | null>(null)
  const faded = r.document.too_short
  return (
    <>
      <div className="doc-head">
        <h3>{t.heatmap}</h3>
        {usable && (
          <div className="legend">
            <span><i style={{ background: '#fff' }} />{t.legendHuman}</span>
            <span><i style={{ background: 'rgba(240,180,0,.45)' }} />{t.legendMixed}</span>
            <span><i style={{ background: 'rgba(226,70,70,.4)' }} />{t.legendAi}</span>
            <label className="toggle"><input type="checkbox" checked={words} onChange={(e) => setWords(e.target.checked)} />{t.showWords}</label>
            <label className="toggle"><input type="checkbox" checked={phrases} onChange={(e) => setPhrases(e.target.checked)} />{t.showPhrases}</label>
          </div>
        )}
      </div>
      <p className="edit-hint">✏️ {t.editHint}</p>
      <div className={`text ${usable ? '' : 'plain'} ${faded ? 'faded' : ''}`} onMouseLeave={() => setTip(null)}>
        {r.paragraphs.map((p, pi) => {
          const orig = r.text.slice(p.start, p.end)
          const edited = edits[pi] !== undefined && edits[pi].trim() !== orig.trim()
          if (editing === pi) {
            return (
              <div key={p.start} className="para-edit">
                <textarea autoFocus value={edits[pi] ?? orig} onChange={(e) => setEdit(pi, e.target.value)}
                  ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight + 4}px` } }} />
                <div className="para-actions">
                  <button className="btn ghost" onClick={() => { setEdit(pi, orig); setEditing(null) }}>↺</button>
                  <button className="btn" onClick={() => setEditing(null)}>{t.done}</button>
                </div>
              </div>
            )
          }
          if (edited) {
            return (
              <p key={p.start} className="para edited" onClick={() => setEditing(pi)}>
                <span className="badge">{t.edited}</span> {edits[pi]}
              </p>
            )
          }
          return (
            <p key={p.start} className="para" onClick={() => setEditing(pi)} title={t.edit}>
              {p.sentences.map((s, i) => (
                <span key={s.start}>
                  {i > 0 && r.text.slice(p.sentences[i - 1].end, s.start)}
                  <motion.span id={`s-${s.start}`} className={`s ${usable ? s.level : ''} ${focus === s.start ? 'focus' : ''}`}
                    initial={{ backgroundColor: 'rgba(0,0,0,0)' }}
                    animate={{ backgroundColor: !usable ? 'rgba(0,0,0,0)' : s.level === 'ai' ? 'rgba(226,70,70,0.2)' : s.level === 'mixed' ? 'rgba(240,180,0,0.26)' : 'rgba(0,0,0,0)' }}
                    transition={{ duration: 0.5, delay: Math.min(1.5, (s.start / Math.max(1, r.text.length)) * 1.5) }}
                    onMouseMove={(e) => usable && setTip({ x: e.clientX, y: e.clientY, s })}>
                    <SentenceBody text={r.text} s={s} words={words && usable} phrases={phrases && usable} />
                  </motion.span>
                </span>
              ))}
            </p>
          )
        })}
      </div>
      {tip && editing === null && <Tooltip tip={tip} t={t} th={r.document.local.red} />}
    </>
  )
}

function SentenceBody({ text, s, words, phrases }: { text: string; s: Sentence; words: boolean; phrases: boolean }) {
  const segs = useMemo(() => {
    const cuts = new Set<number>([s.start, s.end])
    if (words) s.words.forEach(([a, b]) => { cuts.add(a); cuts.add(b) })
    if (phrases) s.phrases.forEach((p) => { cuts.add(p.start); cuts.add(p.end) })
    const pts = [...cuts].filter((x) => x >= s.start && x <= s.end).sort((a, b) => a - b)
    const vals = s.words.map((w) => w[2])
    const lo = Math.min(...vals), hi = Math.max(...vals)
    const out: { a: number; b: number; heat: number | null; ph: boolean }[] = []
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1]
      const w = words ? s.words.find(([x, y]) => x <= a && b <= y) : undefined
      const heat = w && hi > lo ? (w[2] - lo) / (hi - lo) : null
      const ph = phrases && s.phrases.some((p) => p.start <= a && b <= p.end)
      out.push({ a, b, heat, ph })
    }
    return out
  }, [s, words, phrases])
  return (
    <>
      {segs.map(({ a, b, heat, ph }) => (
        <span key={a} className={`${heat !== null ? 'w' : ''} ${ph ? 'ph' : ''}`}
          style={heat !== null ? { background: `rgba(${s.level === 'human' ? '26,127,82' : '210,63,63'},${(heat * heat * 0.45).toFixed(3)})` } : undefined}>
          {text.slice(a, b)}
        </span>
      ))}
    </>
  )
}

function Tooltip({ tip, t, th }: { tip: Tip; t: Strings; th: number }) {
  const { s } = tip
  const left = Math.min(tip.x + 14, window.innerWidth - 300)
  const top = tip.y + 18 + 120 > window.innerHeight ? tip.y - 110 : tip.y + 18
  const label = s.level === 'ai' ? t.legendAi : s.level === 'mixed' ? t.legendMixed : t.legendHuman
  return (
    <motion.div className="tip" style={{ left, top }} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}>
      <b style={{ color: s.level === 'ai' ? '#ff9a9a' : s.level === 'mixed' ? '#ffd56b' : '#8fe0b6' }}>{label}</b>
      <div>{t.sentenceScore}: {s.score?.toFixed(2) ?? '–'} <span style={{ opacity: 0.6 }}>/ {t.threshold} {th.toFixed(2)}</span></div>
      {s.phrases.length > 0 && <div className="ph-list">“{[...new Set(s.phrases.map((p) => p.phrase))].join('”, “')}”</div>}
    </motion.div>
  )
}

/* ---------------- side panels ---------------- */

interface Region { start: number; end: number; first: number; score: number; level: Level; n: number }

/** Consecutive flagged sentences form one region (they usually share one window score). */
function regions(r: Analysis): Region[] {
  const out: Region[] = []
  let cur: Region | null = null
  for (const s of r.paragraphs.flatMap((p) => p.sentences)) {
    if (s.level === 'human') { cur = null; continue }
    const sc = s.score ?? 0
    if (cur) {
      cur.end = s.end; cur.n += 1; cur.score = Math.max(cur.score, sc)
      if (s.level === 'ai') cur.level = 'ai'
    } else {
      cur = { start: s.start, end: s.end, first: s.start, score: sc, level: s.level, n: 1 }
      out.push(cur)
    }
  }
  return out.sort((a, b) => (a.level === b.level ? b.score - a.score : a.level === 'ai' ? -1 : 1)).slice(0, 8)
}

function Suspects({ r, t, onJump }: { r: Analysis; t: Strings; onJump: (start: number) => void }) {
  const list = regions(r)
  return (
    <div className="card panel">
      <h4>{t.suspects}</h4>
      <p className="hint">{t.suspectsHint}</p>
      {list.length === 0 && <p style={{ margin: 0, color: 'var(--ink-2)' }}>{t.noSuspects}</p>}
      {list.map((g, i) => {
        const txt = r.text.slice(g.start, g.end).replace(/\s+/g, ' ')
        return (
          <motion.button key={g.start} className={`suspect ${g.level}`} onClick={() => onJump(g.first)}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.05 }}>
            <div className="sc">{g.score.toFixed(2)} · {g.n} {t.regionSentences}</div>
            {txt.slice(0, 150)}{txt.length > 150 ? '…' : ''}
          </motion.button>
        )
      })}
    </div>
  )
}

function Bars({ items, names }: { items: { label: string; p: number }[]; names: Record<string, string> }) {
  return (
    <>
      {items.slice(0, 3).map((it, i) => (
        <div className="row" key={it.label}>
          <div className="lbl"><span>{names[it.label] ?? it.label}</span><span>{Math.round(it.p * 100)}%</span></div>
          <div className="bar"><motion.div initial={{ width: 0 }} animate={{ width: `${it.p * 100}%` }} transition={{ duration: 0.8, delay: 0.3 + i * 0.1 }} /></div>
        </div>
      ))}
    </>
  )
}

function Resembles({ r, t }: { r: Analysis; t: Strings }) {
  if (r.document.level === 'human') return null
  return (
    <div className="card panel bars">
      <h4>{t.resembles}</h4>
      <p className="hint">{t.resemblesHint}</p>
      <h5>{t.task}</h5>
      <Bars items={r.document.tasks} names={t.ops} />
      <h5>{t.family}</h5>
      <Bars items={r.document.families} names={t.fams} />
    </div>
  )
}

function StylePanel({ r, t }: { r: Analysis; t: Strings }) {
  const s = r.style
  const rows: [string, string, string][] = [
    [t.burstiness, s.burstiness.toFixed(2), t.burstinessHint],
    [t.phrases, String(s.ai_phrases_per_1k), t.phrasesHint],
    [t.emdash, String(s.em_dashes_per_1k), t.emdashHint],
    [t.ttr, s.type_token_ratio.toFixed(2), t.ttrHint],
    [t.avgSentence, `${s.sentence_len_mean} ${t.words}`, ''],
  ]
  return (
    <div className="card panel">
      <h4>{t.style}</h4>
      <p className="hint">{t.styleHint}</p>
      {rows.map(([k, v, h]) => (
        <div className="metric" key={k}>
          <div className="top-line"><span>{k}</span><b>{v}</b></div>
          {h && <small>{h}</small>}
        </div>
      ))}
    </div>
  )
}
