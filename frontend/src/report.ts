import type { Strings } from './i18n'
import type { Analysis } from './types'

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)

/** A self-contained HTML report (prints to PDF from the browser). */
export function buildReport(r: Analysis, t: Strings): string {
  const d = r.document
  const english = d.language?.english !== false
  const pct = (x: number) => `${Math.round(x * 100)}%`
  const verdict = !english ? t.notEnglishTitle : d.too_short ? t.shortTitle : t[`verdict_${d.level}`]
  const body = r.paragraphs.map((p) => {
    const parts = p.sentences.map((s, i) => {
      const gap = i > 0 ? esc(r.text.slice(p.sentences[i - 1].end, s.start)) : ''
      const cls = english ? s.level : ''
      const title = s.score === null ? '' : ` title="${t.sentenceScore}: ${s.score.toFixed(2)}"`
      return `${gap}<span class="${cls}"${title}>${esc(r.text.slice(s.start, s.end))}</span>`
    })
    return `<p>${parts.join('')}</p>`
  }).join('\n')
  const date = new Date().toLocaleString()
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>Definitely Human™ · ${esc(r.source.name ?? 'report')}</title>
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #111418; max-width: 820px; margin: 32px auto; padding: 0 20px; line-height: 1.7; }
  h1 { font-size: 22px; margin: 0; } .muted { color: #6b737c; font-size: 13px; }
  .box { border: 1px solid #e4e7ea; border-radius: 14px; padding: 16px 20px; margin: 18px 0; }
  .stats { display: flex; gap: 28px; flex-wrap: wrap; } .stats b { display: block; font-size: 22px; }
  .ai { background: rgba(226,70,70,.22); } .mixed { background: rgba(240,180,0,.3); }
  .legend span { display: inline-block; padding: 0 8px; border-radius: 4px; margin-right: 8px; font-size: 13px; }
  @media print { body { margin: 0; } .box { break-inside: avoid; } }
</style></head><body>
<h1>✓ Definitely Human™</h1>
<div class="muted">${esc(r.source.name ?? '')} · ${esc(date)} · ${d.n_words} ${t.words}</div>
<div class="box">
  <h2 style="margin:0 0 10px">${esc(verdict)}</h2>
  <div class="stats">
    <div><b style="color:#d23f3f">${pct(d.ai_share)}</b>${t.aiFlagged} ${t.ofText}</div>
    <div><b style="color:#c98a00">${pct(d.mixed_share)}</b>${t.mixedFlagged}</div>
    <div><b>${d.score.toFixed(2)}</b>${t.score} (${t.threshold} ${d.thresholds.strong.toFixed(2)})</div>
  </div>
</div>
<div class="legend"><span class="ai">${t.legendAi}</span><span class="mixed">${t.legendMixed}</span><span>${t.legendHuman}</span></div>
<div class="box">${body}</div>
<p class="muted">${esc(t.disclaimer)}</p>
</body></html>`
}
