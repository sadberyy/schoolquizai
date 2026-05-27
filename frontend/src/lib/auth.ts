import { API_BASE_URL } from "@/lib/api"
import { readApiError } from "@/lib/quizApi"
import type { User } from "@/types/user"

const TOKEN_KEY = "quiz_access_token"
const USER_KEY = "quiz_user"

interface AuthApiResponse {
  access_token: string
  user_id: string
  name: string
  email: string
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function setAuth(accessToken: string, user: User) {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAccessToken()
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export async function authFetch(
  url: string,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers ?? undefined)
  const token = getAccessToken()
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  return fetch(url, {
    ...init,
    headers,
  })
}

function userFromAuthResponse(data: AuthApiResponse): User {
  return {
    id: data.user_id,
    name: data.name,
    email: data.email,
  }
}

export async function loginUser(
  email: string,
  password: string
): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
  })

  if (!response.ok) {
    throw new Error(await readApiError(response, "Неверный email или пароль"))
  }

  const data = (await response.json()) as AuthApiResponse
  const user = userFromAuthResponse(data)
  setAuth(data.access_token, user)
  return user
}

export async function registerUser(
  name: string,
  email: string,
  password: string
): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: name.trim(),
      email: email.trim().toLowerCase(),
      password,
    }),
  })

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось зарегистрироваться"))
  }

  const data = (await response.json()) as AuthApiResponse
  const user = userFromAuthResponse(data)
  setAuth(data.access_token, user)
  return user
}

export async function restoreSession(): Promise<User | null> {
  const token = getAccessToken()
  const stored = getStoredUser()
  if (!token || !stored) return null

  try {
    const response = await authFetch(`${API_BASE_URL}/auth/me`)
    if (!response.ok) {
      clearAuth()
      return null
    }

    const data = (await response.json()) as {
      user_id: string
      name: string
      email: string
    }

    const user: User = {
      id: data.user_id,
      name: data.name,
      email: data.email,
    }
    setAuth(token, user)
    return user
  } catch {
    clearAuth()
    return null
  }
}

export async function downloadAuthenticatedFile(
  url: string,
  fallbackFilename: string
) {
  const response = await authFetch(url)
  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось скачать файл"))
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement("a")
  const contentDisposition = response.headers.get("content-disposition") ?? ""
  const encodedNameMatch = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)
  const plainNameMatch = contentDisposition.match(/filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/i)
  const rawServerName = encodedNameMatch?.[1] ?? plainNameMatch?.[1] ?? plainNameMatch?.[2]
  let resolvedName = fallbackFilename
  if (rawServerName) {
    const normalized = rawServerName.trim()
    try {
      resolvedName = decodeURIComponent(normalized)
    } catch {
      resolvedName = normalized
    }
  }
  link.href = objectUrl
  link.download = resolvedName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
