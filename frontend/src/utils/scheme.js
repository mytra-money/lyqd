/** Fallback illustrative yields when LYQD Settings are blank (not forecasts). */
export const ILLUSTRATIVE_IDLE_YIELD_PCT = 0
export const ILLUSTRATIVE_FD_YIELD_PCT = 3
export const ILLUSTRATIVE_LIQUID_YIELD_PCT = 5.5

const COIN_SLUG_BY_ISIN = {
  // Soft-launch display scheme — Coin page for scheme documents / factsheet
  INF109K01VQ1: 'icici-prudential-liquid-fund-regular-growth',
}

/**
 * Public scheme info page (Zerodha Coin). Prefer known slug; otherwise slugify the label.
 * Opens in a new tab — Coin typically blocks iframes.
 */
export function schemeInfoUrl(isin, label) {
  const code = (isin || '').trim().toUpperCase()
  if (!code) return null
  const known = COIN_SLUG_BY_ISIN[code]
  const slug =
    known ||
    String(label || 'scheme')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') ||
    'scheme'
  return `https://coin.zerodha.com/mf/fund/${encodeURIComponent(code)}/${slug}`
}

/** Interest = Principal × Annual rate × Days ÷ 365 (stated rate only). */
export function illustrativeInterest(principal, annualRatePct, days) {
  const p = Number(principal) || 0
  const r = Number(annualRatePct) || 0
  const d = Math.max(0, Number(days) || 0)
  return Math.round((p * r * d) / 100 / 365)
}

function clampPct(value, fallback) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return fallback
  return Math.min(100, n)
}

/** Resolve Proposal illustration rates from LYQD Settings (boot / get_settings). */
export function resolveIllustrativeRates(settings) {
  const s = settings || {}
  return {
    idle: clampPct(s.illustrative_idle_yield_pct, ILLUSTRATIVE_IDLE_YIELD_PCT),
    fd: clampPct(s.illustrative_fd_yield_pct, ILLUSTRATIVE_FD_YIELD_PCT),
    liquid: clampPct(s.illustrative_liquid_yield_pct, ILLUSTRATIVE_LIQUID_YIELD_PCT),
  }
}

export const MF_DISCLAIMER =
  'Mutual Fund investments are subject to market risks; read all scheme-related documents carefully. Yields shown here are illustrative only and not a guarantee of returns, liquidity, or settlement timing.'
