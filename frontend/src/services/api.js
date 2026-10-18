import axios from 'axios'
import { useAppStore } from './store'

const BASE = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '').replace(/\/api$/, '')

export const api = axios.create({
  baseURL: BASE,
  timeout: 150000,
})

api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && error.config?.headers?.['X-Admin-Token'] && !error.config?.url?.startsWith('/api/chat')) {
    useAppStore.getState().clearAdminAuth()
  }
  return Promise.reject(error)
})

// Add admin token to requests
api.interceptors.request.use(config => {
  try {
    const store = JSON.parse(localStorage.getItem('legal-aid-store') || '{}')
    const token = store?.state?.adminToken
    if (token) config.headers['X-Admin-Token'] = token
  } catch {}
  return config
})

// ── Legal Analysis ────────────────────────────────────────────────────────────
export const analyzeCase = (query, language = 'English', city = '') =>
  api.post('/api/analyze', { query, language, city }).then(r => r.data)

// ── Chat ──────────────────────────────────────────────────────────────────────
let pendingChatSession = null
async function chatSession() {
  const state = useAppStore.getState()
  if (state.chatSessionId && state.chatSessionToken) return { session_id: state.chatSessionId, token: state.chatSessionToken }
  if (!pendingChatSession) {
    pendingChatSession = api.post('/api/chat/sessions').then(({ data }) => {
      useAppStore.getState().setChatSession(data.session_id, data.token)
      return data
    }).finally(() => { pendingChatSession = null })
  }
  return pendingChatSession
}

export const sendChatMessage = async (_sessionId, message, language, caseContext = {}) => {
  for (let attempt = 0; attempt < 2; attempt++) {
    const session = await chatSession()
    try {
      return await api.post('/api/chat', { session_id: session.session_id, message, language, case_context: caseContext },
        { headers: { 'X-Chat-Token': session.token } }).then(r => r.data)
    } catch (error) {
      if (attempt === 0 && error.response?.status === 401) useAppStore.getState().setChatSession(null, null)
      else throw error
    }
  }
}

export const clearChatSession = (sessionId) =>
  api.delete(`/api/chat/${sessionId}`, { headers: { 'X-Chat-Token': useAppStore.getState().chatSessionToken } }).then(r => r.data)

// ── Applications ──────────────────────────────────────────────────────────────
export const submitApplication = (data) =>
  api.post('/api/applications', data).then(r => r.data)

export const getApplications = (params = {}) =>
  api.get('/api/applications', { params }).then(r => r.data)

export const getApplicationStats = () =>
  api.get('/api/applications/stats').then(r => r.data)

export const updateApplicationStatus = (id, status) =>
  api.patch(`/api/applications/${id}/status`, { status }).then(r => r.data)

export const assignLawyer = (id, lawyerId) =>
  api.patch(`/api/applications/${id}/lawyer`, { lawyer_id: lawyerId }).then(r => r.data)

export const assignNGO = (id, ngoId) =>
  api.patch(`/api/applications/${id}/ngo`, { ngo_id: ngoId }).then(r => r.data)

// ── NGOs ──────────────────────────────────────────────────────────────────────
export const getNGOs = (params = {}) =>
  api.get('/api/ngos', { params }).then(r => r.data)

export const createNGO = (data) =>
  api.post('/api/ngos', data).then(r => r.data)

export const updateNGO = (id, data) =>
  api.put(`/api/ngos/${id}`, data).then(r => r.data)

export const deactivateNGO = (id) =>
  api.patch(`/api/ngos/${id}/deactivate`).then(r => r.data)

export const reactivateNGO = (id) =>
  api.patch(`/api/ngos/${id}/reactivate`).then(r => r.data)

export const deleteNGO = (id) =>
  api.delete(`/api/ngos/${id}`).then(r => r.data)

// ── Lawyers ───────────────────────────────────────────────────────────────────
export const getLawyers = (params = {}) =>
  api.get('/api/lawyers', { params }).then(r => r.data)

export const createLawyer = (data) =>
  api.post('/api/lawyers', data).then(r => r.data)

export const updateLawyer = (id, data) =>
  api.put(`/api/lawyers/${id}`, data).then(r => r.data)

export const deleteLawyer = (id) =>
  api.delete(`/api/lawyers/${id}`).then(r => r.data)

export const setLawyerAvailability = (id, available) =>
  api.patch(`/api/lawyers/${id}/availability`, { available }).then(r => r.data)

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getAnalyticsSummary = () =>
  api.get('/api/analytics/summary').then(r => r.data)

export const getQueryLogs = (limit = 500) =>
  api.get('/api/analytics/queries', { params: { limit } }).then(r => r.data)

// ── TTS ───────────────────────────────────────────────────────────────────────
export const getTTSUrl = (text, language) => {
  const params = new URLSearchParams({ text, language })
  return `${BASE}/api/tts?${params}`
}

export const generateTTS = (text, language) =>
  api.post('/api/tts', { text, language }, { responseType: 'blob' }).then(r => r.data)

// ── PDF ───────────────────────────────────────────────────────────────────────
export const downloadPDF = (analysisData, language) =>
  api.post('/api/pdf', { ...analysisData, language }, { responseType: 'blob' }).then(r => r.data)

// ── Transcription ─────────────────────────────────────────────────────────────
export const transcribeAudio = (audioBlob, language) => {
  const form = new FormData()
  const extension = audioBlob.type?.includes('mp4') ? 'mp4' : audioBlob.type?.includes('webm') ? 'webm' : 'wav'
  form.append('audio', audioBlob, `recording.${extension}`)
  form.append('language', language)
  return api.post('/api/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

// ── Routing ───────────────────────────────────────────────────────────────────
export const rerouteApplication = (appId) =>
  api.post(`/api/applications/${appId}/reroute`).then(r => r.data)

export const getRoutingPreview = (city, caseType, urgency = 'Medium') =>
  api.get('/api/routing/preview', { params: { city, case_type: caseType, urgency } }).then(r => r.data)

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminLogin = (password) =>
  api.post('/api/admin/login', { password }).then(r => r.data)

export const adminLogout = () => api.post('/api/admin/logout').then(r => r.data)
export const verifyAdminSession = () => api.get('/api/admin/session').then(r => r.data)

// ── Health ────────────────────────────────────────────────────────────────────
export const checkHealth = (options = {}) =>
  api.get('/api/health', options).then(r => r.data)
