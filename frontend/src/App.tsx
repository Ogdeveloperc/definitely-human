import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { analyzeFile, analyzeText, checkUpdate, getCalib, getStatus, type UpdateInfo } from './api'
import { InputPanel, type Submission } from './components/InputPanel'
import { DrawCheck, Logo } from './components/Logo'
import { Results } from './components/Results'
import { CalibSection, Settings } from './components/Settings'
import { strings, type Lang } from './i18n'
import type { Analysis, Domain, Status } from './types'

type View = 'input' | 'busy' | 'result'

function readPref<T extends string>(key: string, fallback: T): T {
  try { return (localStorage.getItem(key) as T) || fallback } catch { return fallback }
}
function writePref(key: string, v: string) {
  try { localStorage.setItem(key, v) } catch { /* private mode */ }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => readPref('dh.lang', 'tr'))
  const [domain, setDomain] = useState<Domain>(() => readPref('dh.domain', 'essay'))
  const [status, setStatus] = useState<Status | null>(null)
  const [view, setView] = useState<View>('input')
  const [result, setResult] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState(false)
  const [setup, setSetup] = useState(false)
  const [update, setUpdate] = useState<UpdateInfo | null>(null)
  const [progress, setProgress] = useState(0)
  const [prev, setPrev] = useState<Analysis | null>(null)
  const [rescanning, setRescanning] = useState(false)
  const t = strings[lang]

  useEffect(() => { writePref('dh.lang', lang); document.documentElement.lang = lang }, [lang])
  useEffect(() => { writePref('dh.domain', domain) }, [domain])

  useEffect(() => {  // tells the local server this page is still open
    const ping = () => fetch('/api/ping', { method: 'POST' }).catch(() => {})
    ping()
    const id = window.setInterval(ping, 15000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    let stop = false
    const poll = async () => {
      try {
        const s = await getStatus()
        if (stop) return
        setStatus(s)
        if (!s.ready && !s.error) window.setTimeout(poll, 1000)
      } catch {
        if (!stop) window.setTimeout(poll, 1500)
      }
    }
    poll()
    return () => { stop = true }
  }, [])

  useEffect(() => {
    if (!status?.ready) return
    if (readPref<string>('dh.setupSkipped', '') === '1') return
    getCalib().then((c) => setSetup(c.running || !c.result?.created)).catch(() => {})
  }, [status?.ready])

  useEffect(() => {  // quiet update check at start; only the version number is fetched
    if (readPref<string>('dh.autoUpdate', '1') !== '1') return
    checkUpdate().then((u) => u.update && setUpdate(u)).catch(() => {})
  }, [])

  const submit = async (s: Submission) => {
    setError(null)
    setProgress(0)
    setPrev(null)
    setView('busy')
    try {
      const r = s.kind === 'text'
        ? await analyzeText(s.text, domain, setProgress)
        : await analyzeFile(s.file, domain, setProgress)
      setResult(r)
      setView('result')
      window.scrollTo({ top: 0 })
    } catch (e) {
      setError((e as Error).message)
      setView('input')
    }
  }

  /** Re-analyze the edited text in place; the old result stays visible until the new one is ready. */
  const rescan = async (text: string) => {
    if (!result) return
    setProgress(0)
    setRescanning(true)
    try {
      const r = await analyzeText(text, domain, setProgress)
      setPrev(result)
      setResult({ ...r, source: { ...result.source, references_removed: false } })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      window.alert(`${t.error}: ${(e as Error).message}`)
    } finally {
      setRescanning(false)
    }
  }

  const ready = status?.ready
  const dev = status?.device
  return (
    <div className="shell">
      <header className="top">
        <Logo height={34} />
        <div className="top-right">
          <button className="icon-btn" onClick={() => setSettings(true)} disabled={!ready}>⚙︎ {t.settings}</button>
          <div className="lang">
            {(['tr', 'en'] as const).map((l) => (
              <button key={l} className={lang === l ? 'on' : ''} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </header>

      <AnimatePresence>
        {update && (
          <motion.div className="update-banner" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <span>🎉 {t.updateAvailable}: <b>{update.latest}</b> ({t.version.toLowerCase()} {update.current})</span>
            <a className="btn" href={update.url} target="_blank" rel="noreferrer">{t.download}</a>
            <button className="linkish" onClick={() => setUpdate(null)}>{t.close}</button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {!ready ? (
          <motion.div key="loading" className="center" exit={{ opacity: 0 }}>
            <div>
              <DrawCheck size={84} loop={!status?.error} />
              <h2>{status?.error ? t.loadFailed : t.loadingModel}</h2>
              <p>{status?.error ?? t.loadingHint}</p>
            </div>
          </motion.div>
        ) : setup ? (
          <motion.div key="setup" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="hero">
              <DrawCheck size={64} />
              <h1>{t.setupTitle}</h1>
              <p>{t.setupDesc}</p>
            </div>
            <div className="card input-card">
              <CalibSection t={t} onDone={() => window.setTimeout(() => setSetup(false), 2500)} />
            </div>
            <p style={{ textAlign: 'center', marginTop: 14 }}>
              <button className="linkish" onClick={() => { writePref('dh.setupSkipped', '1'); setSetup(false) }}>{t.setupSkip}</button>
            </p>
          </motion.div>
        ) : view === 'input' ? (
          <motion.div key="input" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -10 }}>
            <div className="hero">
              <h1>{lang === 'tr' ? 'Yazın ne kadar “insan”?' : 'How human does it read?'}</h1>
              <p>{t.tagline}</p>
            </div>
            {dev?.warning && <div className="err" style={{ background: '#fff6dc', color: '#6b4b00' }}>⚠️ {t.cpuWarn}</div>}
            <InputPanel t={t} disabled={!ready} domain={domain} setDomain={setDomain} onSubmit={submit} />
            {error && <motion.div className="err" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>{t.error}: {error}</motion.div>}
          </motion.div>
        ) : view === 'busy' ? (
          <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Analyzing label={t.analyzing} hint={t.analyzingHint} progress={progress} />
          </motion.div>
        ) : result ? (
          <motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Results key={result.text.length + ':' + result.document.score} r={result} prev={prev} t={t}
              onReset={() => setView('input')} onRescan={rescan} rescanning={rescanning} progress={progress} />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <Settings t={t} open={settings} onClose={() => setSettings(false)} device={dev ?? null} />

      <footer className="foot">
        <p>{t.disclaimer}</p>
      </footer>
    </div>
  )
}

function Analyzing({ label, hint, progress }: { label: string; hint: string; progress: number }) {
  return (
    <div className="card scan-wrap" style={{ marginTop: 40 }}>
      <motion.div className="scan-bar" initial={{ top: -70 }} animate={{ top: '100%' }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <DrawCheck size={40} loop />
        <div>
          <b style={{ fontSize: 18 }}>{label}<Dots /></b>
          <div style={{ color: 'var(--ink-3)', fontSize: 14 }}>{hint}</div>
        </div>
        <b className="pct">{Math.round(progress * 100)}%</b>
      </div>
      <div className="progress" style={{ marginTop: 14 }}>
        <motion.div animate={{ width: `${Math.max(2, progress * 100)}%` }} transition={{ ease: 'easeOut', duration: 0.4 }} />
      </div>
      <div className="scan-lines">
        {[92, 100, 84, 97, 60, 0, 95, 88, 100, 72].map((w, i) => (
          <motion.span key={i} style={{ width: `${w}%`, visibility: w ? 'visible' : 'hidden' }}
            animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.08 }} />
        ))}
      </div>
    </div>
  )
}

function Dots() {
  return (
    <span>
      {[0, 1, 2].map((i) => (
        <motion.span key={i} animate={{ opacity: [0, 1, 0] }} transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}>.</motion.span>
      ))}
    </span>
  )
}
