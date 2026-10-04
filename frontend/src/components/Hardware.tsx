import { useState } from 'react'
import { openDriverUpdate } from '../api'
import type { Strings } from '../i18n'
import type { Status } from '../types'

type Device = NonNullable<Status['device']>

const fill = (s: string, d: Device) =>
  s.replace('{v}', d.driver_check?.driver ?? '?').replace('{min}', d.driver_check?.driver_min ?? '')

/** True when the user should act on the driver (shown as a banner on the main screen too). */
export const driverNeedsAction = (d: Device | null | undefined) =>
  !!d && (d.driver_check?.status === 'outdated' || d.driver_check?.status === 'cuda_error')

/** Graphics card, NVIDIA driver version and, if needed, a button that opens NVIDIA's own updater. */
export function Hardware({ t, device }: { t: Strings; device: Device }) {
  const [opened, setOpened] = useState<string | null>(null)
  const dc = device.driver_check
  const status = dc?.status ?? (device.device === 'cuda' ? 'ok' : 'no_nvidia')
  const message = {
    ok: device.device === 'cuda' ? t.gpuHint : t.cpuWarn,
    outdated: fill(t.drvOutdated, device),
    cuda_error: fill(t.drvCudaError, device),
    no_nvidia: t.drvNoNvidia,
  }[status]
  const update = async () => {
    try { setOpened((await openDriverUpdate()).opened) } catch { setOpened('web') }
  }
  return (
    <div>
      <div className="row-between">
        <span className={`chip ${device.device === 'cpu' ? 'warn' : ''}`}>
          <span className="dot" />{device.gpu ? `⚡ ${device.gpu}` : (dc?.nvidia_gpu ?? t.cpuMode)}
        </span>
        {device.vram_gb && <span className="count">{device.vram_gb} GB</span>}
      </div>
      {dc?.driver && (
        <div className="row-between">
          <span>{t.drvVersion}: <b>{dc.driver}</b></span>
          <span className={status === 'outdated' ? 'bad' : 'count'}>{t.drvMin}: {dc.driver_min}</span>
        </div>
      )}
      <p className="hint" style={{ color: status === 'ok' ? undefined : '#8a5a00' }}>
        {status === 'ok' && device.device === 'cuda' ? '✓ ' : '⚠️ '}{message}
      </p>
      {(status === 'outdated' || status === 'cuda_error') && (
        <>
          <button className="btn" onClick={update}>{t.drvUpdateBtn}</button>
          <p className="hint" style={{ marginTop: 8 }}>
            {opened === 'nvidia-app' ? t.drvOpenedApp : opened === 'web' ? t.drvOpenedWeb : t.drvWhy}
          </p>
        </>
      )}
    </div>
  )
}
