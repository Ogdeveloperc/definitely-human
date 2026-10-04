import { useState } from 'react'
import { checkUpdate, type UpdateInfo } from '../api'
import type { Strings } from '../i18n'

export function UpdateButton({ t }: { t: Strings }) {
  const [state, setState] = useState<'idle' | 'checking' | 'done' | 'fail'>('idle')
  const [info, setInfo] = useState<UpdateInfo | null>(null)
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem('dh.autoUpdate') !== '0' } catch { return true } })
  const toggle = (v: boolean) => { setAuto(v); try { localStorage.setItem('dh.autoUpdate', v ? '1' : '0') } catch { /* ignore */ } }
  const run = async () => {
    setState('checking')
    try { setInfo(await checkUpdate()); setState('done') } catch { setState('fail') }
  }
  return (
    <>
    <label className="toggle" style={{ marginBottom: 10 }}>
      <input type="checkbox" checked={auto} onChange={(e) => toggle(e.target.checked)} /> {t.autoUpdate}
    </label>
    <div style={{ marginTop: 14, display: 'flex', gap: 10, justifyContent: 'flex-start', alignItems: 'center', flexWrap: 'wrap' }}>
      <button className="btn ghost" onClick={run} disabled={state === 'checking'}>
        {state === 'checking' ? t.checking : t.checkUpdates}
      </button>
      {info && <span>{t.version} {info.current}</span>}
      {state === 'done' && info && !info.update && <span style={{ color: 'var(--green)' }}>{t.upToDate}</span>}
      {state === 'done' && info?.update && (
        <a className="btn" style={{ textDecoration: 'none', padding: '8px 14px', fontSize: 14 }} href={info.url} target="_blank" rel="noreferrer">
          {t.updateAvailable}: {info.latest} — {t.download}
        </a>
      )}
      {state === 'fail' && <span style={{ color: 'var(--red)' }}>{t.updateFailed}</span>}
    </div>
    </>
  )
}
