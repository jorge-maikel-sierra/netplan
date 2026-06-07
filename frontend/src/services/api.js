import axios from 'axios'
import { supabase } from './supabaseClient'
import { getErrorMessage } from '../utils/errorMap'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach Supabase JWT to every request
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// Response interceptor: 401 → signOut + silent redirect to /login
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    const mapped = getErrorMessage(error)
    error.userMessage = mapped.message
    error.errorCode = mapped.code

    return Promise.reject(error)
  }
)

export default api
