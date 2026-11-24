import { Idea, MusicNode, ScriptFormData } from './types'

const BASE = '/api'

async function responseError(response: Response, fallback: string): Promise<Error> {
  const payload = await response.json().catch(() => ({})) as {
    detail?: unknown
    message?: unknown
  }

  let detail = typeof payload.detail === 'string' ? payload.detail : ''
  if (Array.isArray(payload.detail)) {
    detail = payload.detail.map((item: unknown) => {
      if (!item || typeof item !== 'object') return ''
      const issue = item as { loc?: unknown[]; msg?: string }
      const location = Array.isArray(issue.loc) ? issue.loc.slice(1).join('.') : ''
      return [location, issue.msg].filter(Boolean).join(': ')
    }).filter(Boolean).join('; ')
  }
  if (!detail && typeof payload.message === 'string') detail = payload.message

  return new Error(`${detail || fallback} (HTTP ${response.status})`)
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw await responseError(res, `GET ${url} failed`)
  return res.json() as Promise<T>
}

function encodePath(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/')
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw await responseError(res, `POST ${url} failed`)
  return res.json() as Promise<T>
}

async function postJob(url: string, body?: unknown): Promise<string> {
  const { job_id } = await post<{ job_id: string }>(url, body)
  return job_id
}

export const api = {
  ideas: {
    list: (): Promise<Idea[]> => get(`${BASE}/ideas`),
    generate: (): Promise<Idea> => post(`${BASE}/ideas/generate`),
  },

  script: {
    generate: (ideaId: number, form: ScriptFormData) =>
      postJob(`${BASE}/ideas/${ideaId}/script`, form),
    upload: async (ideaId: number, file: File): Promise<void> => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE}/ideas/${ideaId}/script/upload`, { method: 'POST', body: form })
      if (!res.ok) throw await responseError(res, 'Script upload failed')
    },
  },

  audio:    (ideaId: number, force = false) =>
    postJob(`${BASE}/ideas/${ideaId}/audio${force ? '?force=true' : ''}`),
  sync:     (ideaId: number) => postJob(`${BASE}/ideas/${ideaId}/sync`),
  subtitles:(ideaId: number) => postJob(`${BASE}/ideas/${ideaId}/subtitles`),
  assemble: async (ideaId: number, opts: { musicPath: string; bgVolume: number }): Promise<string> => {
    const form = new FormData()
    form.append('bg_volume', String(opts.bgVolume))
    form.append('music_path', opts.musicPath)
    const res = await fetch(`${BASE}/ideas/${ideaId}/assemble`, { method: 'POST', body: form })
    if (!res.ok) throw await responseError(res, 'Video assembly could not be started')
    const { job_id } = await res.json() as { job_id: string }
    return job_id
  },

  music: {
    list: (): Promise<MusicNode[]> => get(`${BASE}/music`),
    upload: async (files: File[], folder = ''): Promise<void> => {
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      if (folder) form.append('folder', folder)
      const res = await fetch(`${BASE}/music/upload`, { method: 'POST', body: form })
      if (!res.ok) throw await responseError(res, 'Music upload failed')
    },
    createFolder: async (name: string, parent = ''): Promise<void> => {
      const form = new FormData()
      form.append('name', name)
      if (parent) form.append('parent', parent)
      const res = await fetch(`${BASE}/music/folder`, { method: 'POST', body: form })
      if (!res.ok) throw await responseError(res, 'Could not create the folder')
    },
    delete: async (path: string): Promise<void> => {
      const res = await fetch(`${BASE}/music/${encodePath(path)}`, { method: 'DELETE' })
      if (!res.ok) throw await responseError(res, 'Could not delete the selected item')
    },
    streamUrl: (path: string) => `${BASE}/music/${encodePath(path)}/stream`,
  },

  geminiKey: {
    check: (): Promise<{ configured: boolean; source: string | null }> =>
      get(`${BASE}/config/gemini-key`),
    save: (key: string): Promise<{ ok: boolean }> =>
      post(`${BASE}/config/gemini-key`, { key }),
  },
}
