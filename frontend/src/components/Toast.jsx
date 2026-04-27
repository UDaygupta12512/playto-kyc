import { createContext, useContext, useState, useCallback, useEffect } from 'react'

const ToastContext = createContext(null)

let _toastFn = null
export const toast = {
  success: (msg, duration) => _toastFn?.('success', msg, duration),
  error:   (msg, duration) => _toastFn?.('error',   msg, duration),
  info:    (msg, duration) => _toastFn?.('info',    msg, duration),
  warning: (msg, duration) => _toastFn?.('warning', msg, duration),
}

const ICONS = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠',
}

const COLORS = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error:   'bg-red-50 border-red-200 text-red-700',
  info:    'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
}

const ICON_COLORS = {
  success: 'bg-green-500',
  error:   'bg-red-500',
  info:    'bg-blue-500',
  warning: 'bg-amber-500',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((type, message, duration = 4000) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, type, message }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), duration)
  }, [])

  useEffect(() => { _toastFn = addToast }, [addToast])

  const remove = (id) => setToasts(t => t.filter(x => x.id !== id))

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map(t => (
          <div key={t.id}
            className={`pointer-events-auto flex items-start gap-3 border rounded-xl px-4 py-3 shadow-lg
              animate-slide-in ${COLORS[t.type]}`}>
            <div className={`w-5 h-5 rounded-full ${ICON_COLORS[t.type]} flex items-center justify-center flex-shrink-0 mt-0.5`}>
              <span className="text-white text-xs font-bold">{ICONS[t.type]}</span>
            </div>
            <span className="text-sm flex-1 leading-snug">{t.message}</span>
            <button onClick={() => remove(t.id)} className="opacity-40 hover:opacity-70 flex-shrink-0 text-xs mt-0.5">✕</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
