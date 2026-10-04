import type { Analysis, Domain, Status } from './types'

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* not json */ }
    throw new Error(msg)
  }
  return r.json()
}

export const getStatus = () => fetch('/api/status').then(json<Status>)

type OnProgress = (f: number) => void

/** Reads the server's NDJSON stream: progress lines, then the result or an error. */
async function streamed(r: Response, onProgress?: OnProgress): Promise<Analysis> {
  if (!r.ok || !r.body) return json<Analysis>(r)
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let nl
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (!line) continue
      const m = JSON.parse(line)
      if ('progress' in m) onProgress?.(m.progress)
      else if ('result' in m) return m.result as Analysis
      else if ('error' in m) throw new Error(m.error)
    }
  }
  throw new Error('Connection closed before the analysis finished.')
}

export const analyzeText = (text: string, domain: Domain, onProgress?: OnProgress) =>
  fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, domain }),
  }).then((r) => streamed(r, onProgress))

export const analyzeFile = (file: File, domain: Domain, onProgress?: OnProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('domain', domain)
  return fetch('/api/analyze-file', { method: 'POST', body: fd }).then((r) => streamed(r, onProgress))
}

/** Ask the server to build a .docx/.txt of the (edited) text and save it. */
export async function exportText(text: string, format: 'docx' | 'txt', name: string) {
  const r = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, format }),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  saveBlob(await r.blob(), `${name}.${format}`)
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export interface UpdateInfo { current: string; latest: string; update: boolean; url: string }

export const checkUpdate = () => fetch('/api/update-check').then(json<UpdateInfo>)

export interface Profile {
  active: boolean
  red?: number
  yellow?: number
  documents?: number
  words?: number
  created?: string
  changed?: boolean
}

export const getProfile = () => fetch('/api/profile').then(json<Profile>)
export const deleteProfile = () => fetch('/api/profile', { method: 'DELETE' }).then(json<Profile>)
export const buildProfile = (files: File[]) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return fetch('/api/profile', { method: 'POST', body: fd }).then(json<Profile>)
}

export interface CalibResult {
  window_words: number
  red: number
  yellow: number
  n_docs: number
  created?: string
  device?: string
  metrics?: {
    sentence_auc_mixed: number
    ai_sentences_caught: number
    human_sentences_red_in_mixed: number
    ai_docs_red_share: number
  }
  doc_fpr?: number
}

export interface CalibStatus {
  running: boolean
  phase?: 'starting' | 'download' | 'prepare' | 'score' | 'choose' | 'done' | 'error'
  progress?: number
  error?: string
  log?: string[]
  result?: CalibResult
}

export const getCalib = () => fetch('/api/calibrate').then(json<CalibStatus>)
export const startCalib = () => fetch('/api/calibrate', { method: 'POST' }).then(json<CalibStatus>)
export const resetCalib = () => fetch('/api/calibrate', { method: 'DELETE' }).then(json<CalibStatus>)
