import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { reviewerAPI, notificationsAPI } from '../api'
import { StateBadge, Spinner, DocTypeName } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { toast } from '../components/Toast'

// Which actions each state exposes to a reviewer
const ACTIONS = {
  submitted:            [{ state: 'under_review',       label: 'Start Review',         style: 'btn-primary',   needsNote: false }],
  under_review:         [
    { state: 'approved',             label: '✓ Approve',            style: 'btn-success',   needsNote: false },
    { state: 'more_info_requested',  label: '📋 Request More Info', style: 'btn-secondary', needsNote: true  },
    { state: 'rejected',             label: '✕ Reject',             style: 'btn-danger',    needsNote: true  },
  ],
  more_info_requested:  [],
  approved:             [],
  rejected:             [],
  draft:                [],
}

// States where we auto-navigate back to queue after transition
const TERMINAL_TRANSITIONS = new Set(['approved', 'rejected', 'more_info_requested'])

export function SubmissionDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const [submission, setSubmission]     = useState(null)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading]           = useState(true)
  const [transitioning, setTransitioning] = useState(false)
  const [note, setNote]                 = useState('')
  const [noteError, setNoteError]       = useState('')
  const [pendingAction, setPendingAction] = useState(null)   // action object user clicked
  const [showDocModal, setShowDocModal] = useState(null)     // doc object to preview

  useEffect(() => {
    Promise.all([
      reviewerAPI.getSubmission(id),
      notificationsAPI.getAll({ submission_id: id }),
    ]).then(([sRes, nRes]) => {
      setSubmission(sRes.data)
      setNotifications(nRes.data)
    }).catch(err => {
      toast.error(err.message)
    }).finally(() => setLoading(false))
  }, [id])

  const handleActionClick = (action) => {
    if (action.needsNote && !note.trim()) {
      setPendingAction(action)
      setNoteError('')
      return
    }
    if (pendingAction && pendingAction.needsNote && !note.trim()) {
      setNoteError('A note is required for this action.')
      return
    }
    executeTransition(action.state)
  }

  const executeTransition = async (newState) => {
    if (ACTIONS[submission.state]?.find(a => a.state === newState && a.needsNote) && !note.trim()) {
      setNoteError('A note is required.')
      return
    }
    setTransitioning(true)
    try {
      const r = await reviewerAPI.transition(id, newState, note)
      setSubmission(r.data)
      setPendingAction(null)
      setNote('')
      const label = { approved: 'Approved', rejected: 'Rejected', more_info_requested: 'More info requested', under_review: 'Review started' }[newState]
      toast.success(`${label} successfully`)

      // Reload notifications
      notificationsAPI.getAll({ submission_id: id }).then(r => setNotifications(r.data)).catch(() => {})

      // Auto-navigate back to queue after terminal actions
      if (TERMINAL_TRANSITIONS.has(newState)) {
        setTimeout(() => navigate('/reviewer'), 1200)
      }
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTransitioning(false)
    }
  }

  if (loading) return (
    <Shell user={user} logout={logout}>
      <div className="flex justify-center py-20"><Spinner size="lg" /></div>
    </Shell>
  )

  if (!submission) return (
    <Shell user={user} logout={logout}>
      <div className="text-center py-20 text-gray-400">Submission not found.</div>
    </Shell>
  )

  const actions = ACTIONS[submission.state] || []

  return (
    <Shell user={user} logout={logout}>
      <div className="max-w-4xl mx-auto py-6 px-4">
        {/* Breadcrumb + header */}
        <div className="mb-5">
          <Link to="/reviewer" className="text-sm text-gray-400 hover:text-gray-600 flex items-center gap-1 w-fit">
            ← Back to Queue
          </Link>
          <div className="flex items-start justify-between mt-3 gap-4">
            <div>
              <h1 className="text-xl font-semibold flex items-center gap-2">
                Submission #{submission.id}
                {submission.is_at_risk && (
                  <span className="badge bg-orange-100 text-orange-600 text-xs">⚠ SLA Risk</span>
                )}
              </h1>
              <p className="text-sm text-gray-500 mt-0.5">
                {submission.merchant?.username}
                {submission.merchant?.email && ` · ${submission.merchant.email}`}
              </p>
            </div>
            <StateBadge state={submission.state} atRisk={submission.is_at_risk} />
          </div>
        </div>

        {/* SLA warning */}
        {submission.is_at_risk && (
          <div className="mb-4 rounded-xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800">
            ⚠ This submission has been waiting for <strong>{submission.queue_age_hours}h</strong> — past the 24-hour SLA target.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: data panels */}
          <div className="lg:col-span-2 space-y-4">
            {/* Personal + Business */}
            <div className="grid grid-cols-2 gap-4">
              <InfoCard title="Personal">
                <DataRow label="Full Name" value={submission.full_name} />
                <DataRow label="Phone"     value={submission.phone} />
                <DataRow label="Email"     value={submission.merchant?.email} />
              </InfoCard>
              <InfoCard title="Business">
                <DataRow label="Name"      value={submission.business_name} />
                <DataRow label="Type"      value={submission.business_type} />
                <DataRow label="Vol/mo"    value={submission.monthly_volume_usd ? `$${Number(submission.monthly_volume_usd).toLocaleString()}` : null} />
              </InfoCard>
            </div>

            {/* Documents */}
            <div className="card p-5">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Documents ({submission.documents?.length || 0}/3)</p>
              {!submission.documents?.length ? (
                <p className="text-sm text-gray-400">No documents uploaded.</p>
              ) : (
                <div className="space-y-2">
                  {submission.documents.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2.5">
                        <span className="text-lg">{doc.doc_type === 'pan' ? '🪪' : doc.doc_type === 'aadhaar' ? '🆔' : '🏦'}</span>
                        <div>
                          <p className="text-sm font-medium">{DocTypeName(doc.doc_type)}</p>
                          <p className="text-xs text-gray-400 font-mono">{doc.original_filename}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-300">{fmtDate(doc.uploaded_at)}</span>
                        <a href={doc.file} target="_blank" rel="noreferrer"
                          className="btn-secondary text-xs py-1 px-3" onClick={e => e.stopPropagation()}>
                          View ↗
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Timeline */}
            <div className="card p-5">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Timeline</p>
              <div className="space-y-2 text-sm">
                <DataRow label="Created"   value={fmt(submission.created_at)} />
                <DataRow label="Submitted" value={fmt(submission.submitted_at)} />
                <DataRow label="Updated"   value={fmt(submission.updated_at)} />
                {submission.assigned_reviewer && (
                  <DataRow label="Reviewer" value={typeof submission.assigned_reviewer === 'object' ? submission.assigned_reviewer.username : `Reviewer #${submission.assigned_reviewer}`} />
                )}
                {submission.queue_age_hours != null && (
                  <DataRow label="Queue age" value={`${submission.queue_age_hours}h`} />
                )}
              </div>
            </div>

            {/* Audit / notifications */}
            {notifications.length > 0 && (
              <div className="card p-5">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Activity Log</p>
                <div className="relative">
                  <div className="absolute left-2 top-0 bottom-0 w-px bg-gray-100" />
                  <div className="space-y-4 pl-6">
                    {notifications.map(n => (
                      <div key={n.id} className="relative">
                        <div className="absolute -left-[18px] w-3 h-3 rounded-full border-2 border-white bg-brand-400" />
                        <p className="text-sm font-medium text-gray-700">{formatEventType(n.event_type)}</p>
                        {n.payload?.reviewer_note && (
                          <p className="text-xs text-gray-500 mt-0.5 italic">"{n.payload.reviewer_note}"</p>
                        )}
                        {n.payload?.reviewer_username && (
                          <p className="text-xs text-gray-400">by {n.payload.reviewer_username}</p>
                        )}
                        <p className="text-xs text-gray-300 mt-0.5">{fmt(n.timestamp)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right: actions panel */}
          <div className="space-y-4">
            {/* Existing reviewer note */}
            {submission.reviewer_note && (
              <div className="card p-4">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Current Reviewer Note</p>
                <p className="text-sm text-gray-700 italic">"{submission.reviewer_note}"</p>
              </div>
            )}

            {/* Actions */}
            {actions.length > 0 ? (
              <div className="card p-4 space-y-4">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Actions</p>

                {/* Note textarea */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">
                    Reviewer Note
                    {pendingAction?.needsNote && <span className="text-red-400 ml-1">*</span>}
                  </label>
                  <textarea
                    className={`input resize-none text-sm ${noteError ? 'border-red-300' : ''}`}
                    rows={3}
                    value={note}
                    onChange={e => { setNote(e.target.value); setNoteError('') }}
                    placeholder={
                      pendingAction?.needsNote
                        ? 'Required — explain what is needed or why…'
                        : 'Optional — add a note for the merchant'
                    }
                  />
                  {noteError && <p className="text-xs text-red-500 mt-1">{noteError}</p>}
                </div>

                <div className="space-y-2">
                  {actions.map(action => (
                    <button key={action.state}
                      className={`${action.style} w-full`}
                      disabled={transitioning}
                      onClick={() => handleActionClick(action)}>
                      {transitioning ? <Spinner /> : action.label}
                    </button>
                  ))}
                </div>

                <div className="text-xs text-gray-300 border-t pt-3">
                  Allowed: {submission.allowed_transitions?.join(', ') || 'none (terminal)'}
                </div>
              </div>
            ) : (
              <div className="card p-4 text-center text-sm text-gray-400">
                <p className="text-2xl mb-1">
                  {submission.state === 'approved' ? '✅' : submission.state === 'rejected' ? '❌' : '—'}
                </p>
                <p>
                  {submission.state === 'approved' ? 'Approved' :
                   submission.state === 'rejected' ? 'Rejected' :
                   submission.state === 'draft' ? 'Merchant hasn\'t submitted yet' :
                   'No actions available'}
                </p>
              </div>
            )}

            {/* Quick nav */}
            <div className="card p-4 space-y-1">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Quick Links</p>
              <Link to="/reviewer" className="block text-sm text-brand-600 hover:underline">← Back to Queue</Link>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  )
}



function Shell({ user, logout, children }) {
  return (
    <div className="min-h-screen bg-surface-50">
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand-500 rounded-lg flex items-center justify-center">
            <span className="text-white text-sm font-bold">P</span>
          </div>
          <span className="font-semibold text-gray-900">Playto Pay</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.username}</span>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}

function InfoCard({ title, children }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</p>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function DataRow({ label, value }) {
  return (
    <div className="flex justify-between gap-2 text-sm">
      <dt className="text-gray-400 flex-shrink-0">{label}</dt>
      <dd className="text-gray-800 font-medium text-right break-all">{value || <span className="text-gray-300">—</span>}</dd>
    </div>
  )
}

function fmt(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}
function fmtDate(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString('en-IN', { dateStyle: 'short' })
}

function formatEventType(type) {
  return {
    kyc_submitted:            '📤 Submitted for review',
    kyc_under_review:         '🔍 Review started',
    kyc_approved:             '✅ Approved',
    kyc_rejected:             '❌ Rejected',
    kyc_more_info_requested:  '📋 More information requested',
  }[type] || type
}
