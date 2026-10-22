import type {Guess, PairSet, Result} from './game'

/** One line of the board. `durationMs` is null for a run with no usable time. */
export type BoardRow = {rank: number; displayName: string; score: number; total: number; durationMs: number | null; isMe: boolean}

export type Today = {
  mode: 'daily' | 'practice'
  dayKey: string | null
  channelName: string | null
  title: string
  subtitle: string | null
  sets: PairSet[]
  myResult: Result | null
  board: BoardRow[]
  nextMatch: string | null
  mugupUrl: string
}

export type Player = {id: string; displayName: string}
export type TokenResponse = {token: string; player: Player}
export type PostResultResponse = {result: Result; recorded: boolean; board: BoardRow[]}

/** An error whose message is a sentence the player can read. */
export class ApiError extends Error {}

const UNREACHABLE = "The game couldn't reach HadithBot's server. Check your connection, then close the game and press Play again."

/**
 * Every call is relative: inside Discord the page is served from <app_id>.discordsays.com,
 * and Discord's proxy only lets requests through to the URL-mapped host. Vercel then
 * rewrites /api/* to the bot's API.
 */
export async function api<T>(path: string, token: string | null, init: {method?: string; body?: unknown} = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      method: init.method ?? 'GET',
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError(UNREACHABLE)
  }

  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const message = body && typeof body === 'object' && 'error' in body && typeof body.error === 'string' ? body.error : null
    throw new ApiError(message ?? `HadithBot's server returned an error (${res.status}). Close the game and press Play again in a minute.`)
  }
  if (body === null) throw new ApiError(`HadithBot's server sent an answer the game couldn't read. Close the game and press Play again in a minute.`)
  return body as T
}

export const getToken = (code: string, guildId: string | null, channelId: string | null) =>
  api<TokenResponse>('/token', null, {method: 'POST', body: {code, guildId, channelId}})

export const getToday = (token: string) => api<Today>('/today', token)

export const postResult = (token: string, dayKey: string, guesses: Guess[], durationMs: number) =>
  api<PostResultResponse>('/result', token, {method: 'POST', body: {dayKey, guesses, durationMs}})
