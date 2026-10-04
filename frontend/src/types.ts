export type Level = 'human' | 'mixed' | 'ai'
export type Domain = 'essay' | 'paper' | 'general'

export interface Phrase { start: number; end: number; phrase: string }

export interface Sentence {
  start: number
  end: number
  score: number | null
  level: Level
  /** [start, end, score] per word */
  words: [number, number, number][]
  phrases: Phrase[]
}

export interface Paragraph { start: number; end: number; score: number; level: Level; sentences: Sentence[] }

export interface Ranked { label: string; p: number }

export interface Analysis {
  source: { kind: 'text' | 'file'; name?: string; references_removed?: boolean; pages?: number; ocr?: string }
  text: string
  document: {
    score: number
    p_ai: number
    level: Level
    thresholds: { domain: string; strong: number; medium: number; weak: number }
    local: { red: number; yellow: number; window_words: number; personal: boolean }
    ai_share: number
    mixed_share: number
    families: Ranked[]
    tasks: Ranked[]
    n_tokens: number
    n_words: number
    too_short: boolean
    language: { english: boolean; en_ratio: number }
  }
  paragraphs: Paragraph[]
  style: {
    words: number
    sentences: number
    sentence_len_mean: number
    sentence_len_sd: number
    burstiness: number
    type_token_ratio: number
    ai_phrases_per_1k: number
    em_dashes_per_1k: number
  }
  runtime: { seconds: number; device: string; gpu?: string; warning?: string }
}

export interface Status {
  ready: boolean
  error: string | null
  device: { device: string; gpu?: string; vram_gb?: number; warning?: string } | null
}
