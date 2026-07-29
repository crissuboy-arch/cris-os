import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { studioApi } from './api'

interface User {
  username: string
  role: string
  display_name: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  hasPermission: (action: string) => boolean
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  hasPermission: () => false,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('studio_token'))
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    if (!token) {
      setLoading(false)
      return
    }
    try {
      // Add token to requests via header
      const me = await fetch('/api/studio/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.json())
      setUser(me)
    } catch {
      localStorage.removeItem('studio_token')
      setToken(null)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { checkAuth() }, [checkAuth])

  const login = async (username: string, password: string) => {
    const res = await studioApi.login(username, password)
    localStorage.setItem('studio_token', res.token)
    setToken(res.token)
    setUser(res.user)
  }

  const logout = () => {
    localStorage.removeItem('studio_token')
    setToken(null)
    setUser(null)
  }

  const hasPermission = (action: string) => {
    if (!user) return false
    const perms: Record<string, string[]> = {
      admin: ['read', 'write', 'delete', 'execute', 'publish', 'manage_users', 'manage_settings'],
      editor: ['read', 'write', 'execute', 'publish'],
      viewer: ['read'],
    }
    return action in (perms[user.role] || [])
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
