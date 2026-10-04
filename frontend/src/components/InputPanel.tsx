import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import type { Strings } from '../i18n'
import type { Domain } from '../types'

export type Submission = { kind: 'text'; text: string } | { kind: 'file'; file: File }

interface Props {
  t: Strings
  disabled: boolean
  domain: Domain
  setDomain: (d: Domain) => void
  onSubmit: (s: Submission) => void
}

const ACCEPT = '.docx,.pdf,.txt,.md'

export function InputPanel({ t, disabled, domain, setDomain, onSubmit }: Props) {
  const [tab, setTab] = useState<'text' | 'file'>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  const ready = tab === 'text' ? words > 0 : file !== null

  const pick = (f: File | undefined) => {
    if (f) { setFile(f); setTab('file') }
  }

  return (
    <motion.div className="card input-card" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]) }}>
      <div className="tabs">
        {(['text', 'file'] as const).map((k) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
            {tab === k && <motion.span layoutId="tabpill" className="pill" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
            {k === 'text' ? t.pasteTab : t.fileTab}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {tab === 'text' ? (
          <motion.div key="text" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <textarea className="paste" value={text} placeholder={t.placeholder} spellCheck={false}
              onChange={(e) => setText(e.target.value)} autoFocus />
          </motion.div>
        ) : (
          <motion.div key="file" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <div className={`drop ${over ? 'over' : ''}`} onClick={() => input.current?.click()}>
              <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => pick(e.target.files?.[0])} />
              {file ? (
                <div className="file-pill" onClick={(e) => e.stopPropagation()}>
                  <FileIcon /> {file.name}
                  <button aria-label="remove" onClick={() => setFile(null)}>×</button>
                </div>
              ) : (
                <div>
                  <motion.div animate={{ y: over ? -6 : 0 }}><FileIcon big /></motion.div>
                  <strong>{t.dropTitle}</strong>
                  {t.dropOr}
                  <div className="types">{t.dropTypes}</div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="actions">
        <div className="seg">
          <span>{t.docType}</span>
          <div className="opts">
            {(['essay', 'paper', 'general'] as const).map((d) => (
              <button key={d} className={domain === d ? 'on' : ''} onClick={() => setDomain(d)}>{t[d]}</button>
            ))}
          </div>
          {tab === 'text' && <span className="count">{words} {t.words}</span>}
        </div>
        <motion.button className="btn" disabled={disabled || !ready} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          onClick={() => onSubmit(tab === 'text' ? { kind: 'text', text } : { kind: 'file', file: file! })}>
          {t.analyze} <span aria-hidden>→</span>
        </motion.button>
      </div>
    </motion.div>
  )
}

function FileIcon({ big }: { big?: boolean }) {
  const s = big ? 44 : 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  )
}
