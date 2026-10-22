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
 * settles. Five seconds is plenty inside Discord.
 */
const READY_TIMEOUT_MS = 5_000

export const OUTSIDE_DISCORD = "Open this from the Play button under HadithBot's daily name match in Discord."

class OutsideDiscord extends Error {}

async function connect(): Promise<Session> {
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID as string | undefined
  if (!clientId) {
    return {status: 'error', message: 'This copy of the game has no Discord client ID. Set VITE_DISCORD_CLIENT_ID and deploy it again.'}
  }

  let sdk: DiscordSDK
  try {
    // Throws straight away when the page wasn't opened by Discord (no frame_id in the URL).
    sdk = new DiscordSDK(clientId)
  } catch {
    return {status: 'outside'}
  }

  try {
    await Promise.race([
      sdk.ready(),
      new Promise((_resolve, reject) => setTimeout(() => reject(new OutsideDiscord()), READY_TIMEOUT_MS)),
    ])
  } catch {
    return {status: 'outside'}
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
  } catch {
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
