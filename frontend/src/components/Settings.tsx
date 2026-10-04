import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import {
  buildProfile, deleteProfile, getCalib, getProfile, resetCalib, startCalib,
  type CalibStatus, type Profile,
} from '../api'
import type { Strings } from '../i18n'
import type { Status } from '../types'
import { UpdateButton } from './UpdateButton'

export function Settings({ t, open, onClose, device }: { t: Strings; open: boolean; onClose: () => void; device: Status['device'] }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="backdrop" onClick={onClose}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside className="drawer" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}>
            <div className="drawer-head">
              <h3>{t.settings}</h3>
              <button className="btn ghost" onClick={onClose}>{t.close}</button>
            </div>
            {device && (
              <section className="set-sec" style={{ borderTop: 0 }}>
                <h4>🖥️ {t.hardware}</h4>
                <div className="row-between">
                  <span className={`chip ${device.device === 'cpu' ? 'warn' : ''}`}>
                    <span className="dot" />{device.gpu ? `⚡ ${device.gpu}` : t.cpuMode}
                  </span>
                </div>
                <p className="hint">{device.device === 'cpu' ? t.cpuWarn : t.gpuHint}</p>
              </section>
            )}
            <ProfileSection t={t} />
            <CalibSection t={t} />
            <section className="set-sec">
              <h4>⟳ {t.checkUpdates}</h4>
              <p className="hint">{t.updateHint}</p>
              <UpdateButton t={t} />
            </section>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

function ProfileSection({ t }: { t: Strings }) {
  const [p, setP] = useState<Profile | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { getProfile().then(setP).catch(() => {}) }, [])

  const learn = async () => {
    setBusy(true); setErr(null); setMsg(null)
    try {
      const r = await buildProfile(files)
      setP(r); setFiles([])
      setMsg(r.changed ? t.profileChanged : t.profileNoChange)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const add = (list: FileList | null) => list && setFiles((f) => [...f, ...Array.from(list)].slice(0, 20))

  return (
    <section className="set-sec">
      <h4>👤 {t.profileTitle} {p?.active && <span className="badge">{t.profileActive}</span>}</h4>
      <p className="hint">{t.profileDesc}</p>
      {p?.active && (
        <div className="row-between">
          <span>{p.documents} {t.profileFrom} · {p.words?.toLocaleString()} {t.words} · {p.created}</span>
          <button className="btn ghost" onClick={async () => { setP(await deleteProfile()); setMsg(null) }}>{t.profileReset}</button>
        </div>
      )}
      <div className="drop small" onClick={() => input.current?.click()}
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files) }}>
        <input ref={input} type="file" multiple accept=".docx,.pdf,.txt,.md" hidden onChange={(e) => add(e.target.files)} />
        {files.length ? (
          <div className="file-list">{files.map((f, i) => <span key={i} className="file-pill">📄 {f.name}</span>)}</div>
        ) : t.profileDrop}
      </div>
      <div className="row-between">
        <span className="count">{files.length ? `${files.length} ${t.profileFrom}` : ''}</span>
        <button className="btn" disabled={files.length < 3 || busy} onClick={learn}>
          {busy ? t.profileLearning : t.profileLearn}
        </button>
      </div>
      {msg && <div className="ok-msg">✓ {msg}</div>}
      {err && <div className="err" style={{ margin: '10px 0 0' }}>{err}</div>}
    </section>
  )
}

export function CalibSection({ t, onDone }: { t: Strings; onDone?: () => void }) {
  const [st, setSt] = useState<CalibStatus | null>(null)
  useEffect(() => {
    let alive = true
    let timer = 0
    const poll = async () => {
      try {
        const s = await getCalib()
        if (!alive) return
        setSt(s)
        if (s.running) timer = window.setTimeout(poll, 1500)
        else if (s.phase === 'done') onDone?.()
      } catch { /* server restarting */ }
    }
    poll()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [st?.running, onDone])

  const m = st?.result?.metrics
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`
  return (
    <section className="set-sec">
      <h4>🎯 {t.calibTitle}</h4>
      <p className="hint">{t.calibDesc}</p>
      {st?.running ? (
        <div>
          <div className="row-between"><b>{t.calibPhase[st.phase ?? 'starting']}…</b><span>{Math.round((st.progress ?? 0) * 100)}%</span></div>
          <div className="progress"><motion.div animate={{ width: `${(st.progress ?? 0) * 100}%` }} /></div>
          <pre className="log">{(st.log ?? []).join('\n')}</pre>
        </div>
      ) : (
        <>
          <div className="row-between">
            <span className={st?.result?.created ? 'badge' : 'count'}>{st?.result?.created ? `${t.calibDone} · ${st.result.created}` : t.calibShipped}</span>
          </div>
          {st?.phase === 'error' && <div className="err" style={{ margin: '10px 0' }}>{st.error}</div>}
          {m && (
            <div className="metrics">
              <Metric label={t.mCaught} value={pct(m.ai_sentences_caught)} good />
              <Metric label={t.mFalse} value={pct(m.human_sentences_red_in_mixed)} />
              {st?.result?.doc_fpr !== undefined && <Metric label={t.mDocFpr} value={`≤ ${pct(st.result.doc_fpr)}`} />}
              <Metric label={t.mAuc} value={m.sentence_auc_mixed.toFixed(3)} good />
            </div>
          )}
          <div className="row-between" style={{ marginTop: 12 }}>
            {st?.result?.created ? <button className="btn ghost" onClick={async () => setSt(await resetCalib())}>{t.calibReset}</button> : <span />}
            <button className="btn" onClick={async () => setSt(await startCalib())}>{t.calibStart}</button>
          </div>
        </>
      )}
    </section>
  )
}

function Metric({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="metric">
      <div className="top-line"><span>{label}</span><b style={{ color: good ? 'var(--green)' : 'var(--ink)' }}>{value}</b></div>
    </div>
  )
}
