import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { authAPI } from '../api'
import { Spinner } from '../components/ui'
import { toast } from '../components/Toast'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const user = await login(form.username, form.password)
      toast.success(`Welcome back, ${user.username}!`)
      navigate(user.role === 'reviewer' ? '/reviewer' : '/kyc')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }


  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your Playto account">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input className="input" value={form.username} autoComplete="username"
            onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
            placeholder="your_username" required />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input className="input" type="password" value={form.password} autoComplete="current-password"
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            placeholder="••••••••" required />
        </div>
        <button className="btn-primary w-full" disabled={loading}>
          {loading ? <><Spinner /> Signing in…</> : 'Sign In'}
        </button>
        <p className="text-center text-sm text-gray-500">
          No account? <Link to="/register" className="text-brand-600 hover:underline font-medium">Register as merchant</Link>
        </p>
      </form>

    </AuthLayout>
  )
}

export function RegisterPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'merchant' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const validate = () => {
    const e = {}
    if (!form.username.trim()) e.username = 'Username is required'
    else if (!/^[a-zA-Z0-9_]{3,30}$/.test(form.username)) e.username = '3-30 chars, letters/numbers/underscore only'
    if (!form.password) e.password = 'Password is required'
    else if (form.password.length < 6) e.password = 'Minimum 6 characters'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setLoading(true)
    try {
      const r = await authAPI.register(form)
      localStorage.setItem('token', r.data.token)
      toast.success('Account created! Complete your KYC to get started.')
      navigate(r.data.user.role === 'reviewer' ? '/reviewer' : '/kyc')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const set = (field) => (e) => {
    setForm(f => ({ ...f, [field]: e.target.value }))
    setErrors(v => ({ ...v, [field]: '' }))
  }

  return (
    <AuthLayout title="Create account" subtitle="Start your KYC onboarding with Playto Pay">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username <span className="text-red-400">*</span></label>
          <input className={`input ${errors.username ? 'border-red-300' : ''}`}
            value={form.username} autoComplete="username"
            onChange={set('username')} placeholder="e.g. priya_sharma" />
          {errors.username && <p className="text-xs text-red-500 mt-1">{errors.username}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input className="input" type="email" value={form.email} autoComplete="email"
            onChange={set('email')} placeholder="priya@example.com" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password <span className="text-red-400">*</span></label>
          <input className={`input ${errors.password ? 'border-red-300' : ''}`}
            type="password" value={form.password} autoComplete="new-password"
            onChange={set('password')} placeholder="Min 6 characters" />
          {errors.password && <p className="text-xs text-red-500 mt-1">{errors.password}</p>}
        </div>
        <button className="btn-primary w-full" disabled={loading}>
          {loading ? <><Spinner /> Creating account…</> : 'Create Account'}
        </button>
        <p className="text-center text-sm text-gray-500">
          Already have an account? <Link to="/login" className="text-brand-600 hover:underline font-medium">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

function AuthLayout({ title, subtitle, children }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-surface-100 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-brand-500 rounded-2xl mb-4 shadow-lg shadow-brand-200">
            <span className="text-white text-xl font-bold">P</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-400 mt-1">{subtitle}</p>
        </div>
        <div className="card p-6 shadow-sm">{children}</div>
        <p className="text-center text-xs text-gray-300 mt-4">Playto Pay · KYC Pipeline</p>
      </div>
    </div>
  )
}
