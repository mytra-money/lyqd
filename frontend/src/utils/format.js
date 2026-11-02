export function formatINR(amount, fractionDigits = 0) {
  const n = Number(amount || 0)
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(n)
}

export function formatINRCompact(amount) {
  const n = Number(amount || 0)
  const abs = Math.abs(n)
  if (abs >= 1e7) return `${n < 0 ? '-' : ''}₹${(abs / 1e7).toFixed(2)} Cr`
  if (abs >= 1e5) return `${n < 0 ? '-' : ''}₹${(abs / 1e5).toFixed(2)} L`
  return formatINR(n)
}

export function formatDate(value) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(value))
  } catch {
    return String(value)
  }
}
