export const STATE_CONFIG = {
  draft:                { label: 'Draft',               color: 'bg-gray-100 text-gray-600',    dot: 'bg-gray-400' },
  submitted:            { label: 'Submitted',           color: 'bg-blue-100 text-blue-700',    dot: 'bg-blue-500' },
  under_review:         { label: 'Under Review',        color: 'bg-purple-100 text-purple-700', dot: 'bg-purple-500' },
  approved:             { label: 'Approved',            color: 'bg-green-100 text-green-700',  dot: 'bg-green-500' },
  rejected:             { label: 'Rejected',            color: 'bg-red-100 text-red-700',      dot: 'bg-red-500' },
  more_info_requested:  { label: 'More Info Needed',    color: 'bg-amber-100 text-amber-700',  dot: 'bg-amber-500' },
}

export function StateBadge({ state, atRisk }) {
  const cfg = STATE_CONFIG[state] || { label: state, color: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400' }
  return (
    <span className="inline-flex items-center gap-1.5 flex-wrap">
      <span className={`badge ${cfg.color} gap-1.5`}>
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        {cfg.label}
      </span>
      {atRisk && (
        <span className="badge bg-orange-100 text-orange-700">⚠ SLA Risk</span>
      )}
    </span>
  )
}

export function Spinner({ size = 'sm' }) {
  const s = size === 'sm' ? 'h-4 w-4' : 'h-7 w-7'
  return (
    <svg className={`animate-spin ${s} text-current`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}

export function Alert({ type = 'error', message, onClose }) {
  if (!message) return null
  const colors = {
    error:   'bg-red-50 border-red-200 text-red-700',
    success: 'bg-green-50 border-green-200 text-green-700',
    info:    'bg-blue-50 border-blue-200 text-blue-700',
    warning: 'bg-amber-50 border-amber-200 text-amber-700',
  }
  const icons = { error: '✕', success: '✓', info: 'ℹ', warning: '⚠' }
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm flex items-start gap-2.5 ${colors[type]}`}>
      <span className="flex-shrink-0 font-bold mt-0.5">{icons[type]}</span>
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose} className="opacity-40 hover:opacity-70 flex-shrink-0 ml-1">✕</button>
      )}
    </div>
  )
}

export function DocTypeName(type) {
  return { pan: 'PAN Card', aadhaar: 'Aadhaar Card', bank_statement: 'Bank Statement' }[type] || type
}
