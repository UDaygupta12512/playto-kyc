import axios from 'axios'

const BASE = '/api/v1'

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const data = err.response?.data
    const msg = data?.message || data?.detail || err.message || 'An unexpected error occurred.'
    const enhanced = new Error(msg)
    enhanced.status = err.response?.status
    enhanced.data = data
    return Promise.reject(enhanced)
  }
)

export const authAPI = {
  register: (data) => api.post('/auth/register/', data),
  login:    (data) => api.post('/auth/login/', data),
  me:       ()     => api.get('/auth/me/'),
}

export const merchantAPI = {
  getSubmission:    ()           => api.get('/kyc/submission/'),
  updateSubmission: (data)       => api.patch('/kyc/submission/', data),
  submit:           ()           => api.post('/kyc/submit/'),
  uploadDocument:   (docType, file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/kyc/documents/${docType}/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteDocument:   (docType)    => api.delete(`/kyc/documents/${docType}/`),
}

export const reviewerAPI = {
  getQueue:       (state = 'active') => api.get('/reviewer/queue/', { params: { state } }),
  getSubmission:  (id)               => api.get(`/reviewer/submissions/${id}/`),
  transition:     (id, new_state, reviewer_note = '') =>
                    api.post(`/reviewer/submissions/${id}/transition/`, { new_state, reviewer_note }),
  getMetrics:     ()                 => api.get('/reviewer/metrics/'),
}

export const notificationsAPI = {
  getAll:         (params = {})      => api.get('/notifications/', { params }),
}

export default api
