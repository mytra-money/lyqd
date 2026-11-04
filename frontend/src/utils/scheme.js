/** Illustrative liquid-fund yield shown on Proposal (not a guarantee). */
export const ILLUSTRATIVE_LIQUID_YIELD_PCT = 6.5

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

export const MF_DISCLAIMER =
  'Mutual Fund investments are subject to market risks; read all scheme-related documents carefully. Yields shown here are illustrative only and not a guarantee of returns, liquidity, or settlement timing.'
