import {useCallback, useEffect, useRef, useState} from 'react'
import {ApiError, getToday, postResult, type BoardRow, type Today} from './api'
import {OUTSIDE_DISCORD, SLOW_MS, useDiscordSession} from './discord'
import {allGuesses, revealedIds, scoreGame, type Guess, type Result as GameResult} from './game'
import {TodaysGames} from './GameCards'
import {wording, type GameKey} from './games'
import {channelLabel, Play, SoundToggle} from './Play'
import {Result, type ResultVariant} from './Result'
import {unlockAudio} from './sound'
import {Button, Kbd, MUGUP_DISCORD_URL, Notice, Page, Panel, PoweredByMugup, useFinePointer} from './ui'

type Phase =
  | {name: 'loading'}
  | {name: 'loadError'; message: string}
  /** `focusStart`: the player switched games, so keyboard focus goes to the new start button. */
  | {name: 'start'; today: Today; focusStart: boolean}
  | {name: 'playing'; today: Today; startedAt: number}
  | {name: 'posting'; today: Today; guesses: Guess[]; durationMs: number; error: string | null}
  | {name: 'result'; today: Today; result: GameResult; board: BoardRow[]; variant: ResultVariant; revealed: number[] | null}

const readable = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback)

function isPlayable(today: Today) {
  return today.sets.length > 0 && today.sets.every((s) => s.pairs.length > 0)
}

export default function App() {
  const session = useDiscordSession()

  if (session.status === 'connecting') return <Connecting />
  if (session.status === 'outside') return <Notice title="HadithBot name match">{OUTSIDE_DISCORD}</Notice>
  if (session.status === 'error') return <Notice title="The game couldn't start">{session.message}</Notice>
  return <Game token={session.token} openExternal={session.openExternal} />
}

function Connecting() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_MS)
    return () => clearTimeout(t)
  }, [])
  return (
    <Notice busy>
      <p>Signing you in with Discord...</p>
      {slow && <p className="mt-2 text-[#98a2b3]">Still waiting for Discord to answer. In a web browser this can take up to 30 seconds.</p>}
    </Notice>
  )
}

function Game({token, openExternal}: {token: string; openExternal: (url: string) => Promise<void>}) {
  const [phase, setPhase] = useState<Phase>({name: 'loading'})

  /** The game last asked for, so "Try loading the match again" retries the same one. */
  const lastGame = useRef<GameKey | undefined>(undefined)

  /**
   * Loads one game's match. Every game switch comes through here, so play state starts
   * fresh: the playing phase (timer, guesses, sounds) only exists until the next load.
   */
  const load = useCallback(async (game?: GameKey, switched = false) => {
    lastGame.current = game
    setPhase({name: 'loading'})
    try {
      const today = await getToday(token, game)
      if (today.myResult) {
        setPhase({name: 'result', today, result: today.myResult, board: today.board, variant: 'alreadyPlayed', revealed: null})
      } else if (!isPlayable(today)) {
        setPhase({name: 'loadError', message: wording(today.game).empty})
      } else {
        setPhase({name: 'start', today, focusStart: switched})
      }
    } catch (err) {
      setPhase({name: 'loadError', message: readable(err, "The game couldn't load today's match.")})
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])

  const post = useCallback(
    async (today: Today, guesses: Guess[], durationMs: number) => {
      setPhase({name: 'posting', today, guesses, durationMs, error: null})
      try {
        if (!today.dayKey) throw new ApiError("This match has no date, so the score can't be posted. Close the game and press Play again.")
        const res = await postResult(token, today.game ?? 'names', today.dayKey, guesses, durationMs)
        // recorded: false means an earlier run was returned, so this run's reveals don't apply to it.
        const revealed = res.recorded ? revealedIds([guesses]) : null
        setPhase({name: 'result', today, result: res.result, board: res.board, variant: res.recorded ? 'posted' : 'alreadyPlayed', revealed})
      } catch (err) {
        setPhase({name: 'posting', today, guesses, durationMs, error: readable(err, "The game couldn't post your score.")})
      }
    },
    [token],
  )

  const openMugup = (url: string) => {
    openExternal(url).catch(() => {
      // Discord shows its own "leaving Discord" prompt; a refusal there needs no message from us.
    })
  }

  switch (phase.name) {
    case 'loading':
      return <Notice busy>Loading today's match...</Notice>

    case 'loadError':
      return (
        <Notice title="The game couldn't load the match" action={<Button onClick={() => void load(lastGame.current)}>Try loading the match again</Button>}>
          {phase.message}
        </Notice>
      )

    case 'start':
      return (
        <Start
          key={phase.today.game}
          today={phase.today}
          focusStart={phase.focusStart}
          onOpenGame={(game) => void load(game, true)}
          onStart={() => {
            unlockAudio()
            setPhase({name: 'playing', today: phase.today, startedAt: Date.now()})
          }}
          onOpenMugupDiscord={() => openMugup(MUGUP_DISCORD_URL)}
        />
      )

    case 'playing':
      return (
        <Play
          key={`${phase.today.game}-${phase.startedAt}`}
          today={phase.today}
          startedAt={phase.startedAt}
          onFinish={(state, durationMs) => {
            if (phase.today.mode === 'practice') {
              setPhase({
                name: 'result',
                today: phase.today,
                result: scoreGame(state.sets, state.guesses, durationMs),
                board: [],
                variant: 'practice',
                revealed: revealedIds(state.guesses),
              })
            } else {
              void post(phase.today, allGuesses(state), durationMs)
            }
          }}
        />
      )

    case 'posting':
      if (!phase.error) return <Notice busy>Posting your score...</Notice>
      return (
        <Notice
          title="Your score wasn't posted yet"
          action={
            <Button variant="primary" onClick={() => void post(phase.today, phase.guesses, phase.durationMs)}>
              Try posting my score again
            </Button>
          }>
          {phase.error}
        </Notice>
      )

    case 'result':
      return (
        <Result
          today={phase.today}
          result={phase.result}
          board={phase.board}
          variant={phase.variant}
          revealed={phase.revealed}
          onOpenMugup={() => openMugup(phase.today.mugupUrl)}
          onOpenMugupDiscord={() => openMugup(MUGUP_DISCORD_URL)}
          onPracticeAgain={() => void load(phase.today.game, true)}
          onOpenGame={(game) => void load(game, true)}
        />
      )
  }
}

function Start({
  today,
  focusStart,
  onStart,
  onOpenGame,
  onOpenMugupDiscord,
}: {
  today: Today
  focusStart: boolean
  onStart: () => void
  onOpenGame: (game: GameKey) => void
  onOpenMugupDiscord: () => void
}) {
  const practice = today.mode === 'practice'
  const w = wording(today.game)
  const finePointer = useFinePointer()
  const begin = useRef(onStart)
  begin.current = onStart
  const startButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (focusStart) startButton.current?.focus()
  }, [focusStart])

  // Enter starts, unless a different button has focus (the browser presses that one).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || e.repeat || e.metaKey || e.ctrlKey || e.altKey) return
      if (document.activeElement instanceof HTMLButtonElement) return
      e.preventDefault()
      begin.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const rules = w.rules

  return (
    <Page label={w.header} place={practice ? 'Practice' : channelLabel(today)} headerRight={<SoundToggle />}>
      <Panel className="anim-rise px-5 py-9 text-center sm:px-10 sm:py-12">
        <h1 className="mb-1.5 text-xl font-bold tracking-tight text-white sm:text-[28px]">{today.title}</h1>
        {today.subtitle && <p className="mx-auto mb-4 max-w-[600px] text-[#98a2b3]">{today.subtitle}</p>}
        <div className="mx-auto mb-6 mt-3 flex max-w-[260px] items-center justify-center gap-2" aria-hidden>
          <span className="flex-1 rounded-lg border-[1.5px] border-name-line bg-name-bg px-2 py-2 text-xs font-semibold text-[#f1f4f8]">{w.sample}</span>
          <span className="text-[#7f8a9a]">+</span>
          <span className="flex-1 rounded-lg border-[1.5px] border-mean-line bg-mean-bg px-2 py-2 text-xs font-semibold text-[#fbe6cf]">Its meaning</span>
        </div>
        <p className="mx-auto mb-7 max-w-[600px] text-[#c9d1dc]">
          {practice ? (
            <>
              There's no daily match in this channel, so this round isn't scored or posted anywhere. Daily matches come with the hadith in channels where a
              server admin has set up HadithBot. {rules}
            </>
          ) : (
            <>
              {rules} You have one try today. If two people get the same score, the faster time ranks higher.
            </>
          )}
        </p>
        <Button ref={startButton} variant="primary" className="px-6 py-3 text-base" onClick={onStart}>
          {practice ? 'Start a practice round' : 'Start the timer and play'}
          {finePointer && <Kbd>Enter</Kbd>}
        </Button>
      </Panel>
      <TodaysGames today={today} onOpen={onOpenGame} />
      <PoweredByMugup onOpen={onOpenMugupDiscord} />
    </Page>
  )
}
