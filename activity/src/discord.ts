import {useEffect, useState} from 'react'
import {DiscordSDK} from '@discord/embedded-app-sdk'
import {ApiError, getToken, type Player} from './api'

/**
 * The Embedded App SDK handshake, simplified from MugUp's use-activity-session.ts:
 *
 *   1. sdk.ready(): Discord says the frame is alive.
 *   2. authorize(): a one-time OAuth code for the identify scope.
 *   3. POST /api/token: the server swaps the code for the player's identity and returns
 *      our own session token. The guild and channel are sealed into that token.
 *
 * authenticate() is skipped: the server doesn't hand back a Discord access token, and v1
 * has no rich presence that would need one.
 *
 * The token lives in memory only. A relaunch redoes the handshake in under a second.
 */

export type Session =
  | {status: 'connecting'}
  | {status: 'outside'}
  | {status: 'error'; message: string}
  | {status: 'ready'; token: string; player: Player; openExternal: (url: string) => Promise<void>}

/**
 * Opened in a normal browser tab, ready() posts to a parent window that isn't there and never
 * settles. The Discord desktop app answers in well under a second, but Discord in a web browser
 * can take longer, so the game waits this long before giving up. The screen says it's still
 * waiting after SLOW_MS.
 */
const READY_TIMEOUT_MS = 30_000
export const SLOW_MS = 5_000

/** Origins of the window messages the page received, for the failure report. */
const seenOrigins = new Set<string>()
window.addEventListener('message', (e) => {
  if (seenOrigins.size < 8) seenOrigins.add(e.origin)
})

/**
 * Tell the bot why the game couldn't start, so a failure on someone else's screen shows up in
 * the bot's logs. Best effort: nothing on screen depends on it.
 */
function report(reason: string, error?: unknown) {
  const params = new URLSearchParams(window.location.search)
  const detail = {
    reason,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    params: [...params.keys()].join(','),
    platform: params.get('platform'),
    referrer: document.referrer ? new URL(document.referrer).origin : '',
    framed: window.parent !== window,
    opener: Boolean(window.parent.opener),
    origins: [...seenOrigins].join(','),
    ua: navigator.userAgent.slice(0, 160),
  }
  try {
    const body = JSON.stringify(detail)
    if (!navigator.sendBeacon?.('/api/client-log', new Blob([body], {type: 'application/json'}))) {
      void fetch('/api/client-log', {method: 'POST', body, headers: {'Content-Type': 'application/json'}, keepalive: true})
    }
  } catch {
    // reporting must never break the screen
  }
}

export const OUTSIDE_DISCORD = "Open this from the Play button under HadithBot's daily name match in Discord."

class OutsideDiscord extends Error {
  constructor() {
    super(`no answer from Discord after ${READY_TIMEOUT_MS / 1000}s`)
  }
}

async function connect(): Promise<Session> {
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID as string | undefined
  if (!clientId) {
    return {status: 'error', message: 'This copy of the game has no Discord client ID. Set VITE_DISCORD_CLIENT_ID and deploy it again.'}
  }

  let sdk: DiscordSDK
  try {
    // Throws straight away when the page wasn't opened by Discord (no frame_id in the URL).
    sdk = new DiscordSDK(clientId)
  } catch (err) {
    report('no-launch-params', err)
    return {status: 'outside'}
  }

  try {
    await Promise.race([
      sdk.ready(),
      new Promise((_resolve, reject) => setTimeout(() => reject(new OutsideDiscord()), READY_TIMEOUT_MS)),
    ])
  } catch (err) {
    report('ready-timeout', err)
    return {
      status: 'error',
      message: "Discord didn't answer the game. Close the game and press Play again. If it keeps happening in a web browser, try the Discord app.",
    }
  }

  let code: string
  try {
    ;({code} = await sdk.commands.authorize({
      client_id: clientId,
      response_type: 'code',
      state: '',
      prompt: 'none',
      scope: ['identify'],
    }))
  } catch (err) {
    report('authorize-failed', err)
    return {
      status: 'error',
      message: "Discord didn't sign you in, so the game can't tell who's playing. Close the game, press Play again, and choose Authorize when Discord asks.",
    }
  }

  try {
    const {token, player} = await getToken(code, sdk.guildId, sdk.channelId)
    return {
      status: 'ready',
      token,
      player,
      openExternal: async (url: string) => {
        await sdk.commands.openExternalLink({url})
      },
    }
  } catch (err) {
    return {status: 'error', message: err instanceof ApiError ? err.message : "The game couldn't sign you in. Close the game and press Play again."}
  }
}

// One handshake per page load, even if React runs the effect twice.
let pending: Promise<Session> | null = null

export function useDiscordSession(): Session {
  const [session, setSession] = useState<Session>({status: 'connecting'})
  useEffect(() => {
    let cancelled = false
    pending ??= connect()
    pending.then((s) => {
      if (!cancelled) setSession(s)
    })
    return () => {
      cancelled = true
    }
  }, [])
  return session
}
