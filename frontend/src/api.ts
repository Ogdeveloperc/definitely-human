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

export const analyzeText = (text: string, domain: Domain) =>
  fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, domain }),
  }).then(json<Analysis>)

export const analyzeFile = (file: File, domain: Domain) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('domain', domain)
  return fetch('/api/analyze-file', { method: 'POST', body: fd }).then(json<Analysis>)
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
