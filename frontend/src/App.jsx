import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { ToastProvider } from './components/Toast'
import { LoginPage, RegisterPage } from './pages/Auth'
import { KYCPage } from './pages/KYC'
import { ReviewerDashboard } from './pages/ReviewerDashboard'
import { SubmissionDetail } from './pages/SubmissionDetail'
import { Spinner } from './components/ui'

function ProtectedRoute({ children, requireRole }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><Spinner size="lg" /></div>
  if (!user) return <Navigate to="/login" replace />
  if (requireRole && user.role !== requireRole) {
    return <Navigate to={user.role === 'reviewer' ? '/reviewer' : '/kyc'} replace />
  }
  return children
}

function RootRedirect() {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><Spinner size="lg" /></div>
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'reviewer' ? '/reviewer' : '/kyc'} replace />
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/kyc" element={
              <ProtectedRoute requireRole="merchant"><KYCPage /></ProtectedRoute>
            } />
            <Route path="/reviewer" element={
              <ProtectedRoute requireRole="reviewer"><ReviewerDashboard /></ProtectedRoute>
            } />
            <Route path="/reviewer/submission/:id" element={
              <ProtectedRoute requireRole="reviewer"><SubmissionDetail /></ProtectedRoute>
            } />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  )
}
