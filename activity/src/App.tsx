import {useCallback, useEffect, useState} from 'react'
import {ApiError, getToday, postResult, type BoardRow, type Today} from './api'
import {OUTSIDE_DISCORD, useDiscordSession} from './discord'
import {allGuesses, scoreGame, type Guess, type Result as GameResult} from './game'
import {Play} from './Play'
import {Result, type ResultVariant} from './Result'
import {Button, Notice, Page} from './ui'

type Phase =
  | {name: 'loading'}
  | {name: 'loadError'; message: string}
  | {name: 'start'; today: Today}
  | {name: 'playing'; today: Today; startedAt: number}
  | {name: 'posting'; today: Today; guesses: Guess[]; durationMs: number; error: string | null}
  | {name: 'result'; today: Today; result: GameResult; board: BoardRow[]; variant: ResultVariant}

const readable = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback)

function isPlayable(today: Today) {
  return today.sets.length > 0 && today.sets.every((s) => s.pairs.length > 0)
}

export default function App() {
  const session = useDiscordSession()

  if (session.status === 'connecting') return <Notice>Signing you in with Discord...</Notice>
  if (session.status === 'outside') return <Notice title="HadithBot name match">{OUTSIDE_DISCORD}</Notice>
  if (session.status === 'error') return <Notice title="The game couldn't start">{session.message}</Notice>
  return <Game token={session.token} openExternal={session.openExternal} />
}

function Game({token, openExternal}: {token: string; openExternal: (url: string) => Promise<void>}) {
  const [phase, setPhase] = useState<Phase>({name: 'loading'})

  const load = useCallback(async () => {
    setPhase({name: 'loading'})
    try {
      const today = await getToday(token)
      if (today.myResult) {
        setPhase({name: 'result', today, result: today.myResult, board: today.board, variant: 'alreadyPlayed'})
      } else if (!isPlayable(today)) {
        setPhase({name: 'loadError', message: "Today's match has no names in it. Close the game and press Play again later."})
      } else {
        setPhase({name: 'start', today})
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
        const res = await postResult(token, today.dayKey, guesses, durationMs)
        setPhase({name: 'result', today, result: res.result, board: res.board, variant: res.recorded ? 'posted' : 'alreadyPlayed'})
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
      return <Notice>Loading today's match...</Notice>

    case 'loadError':
      return (
        <Notice title="The game couldn't load the match" action={<Button onClick={() => void load()}>Try loading the match again</Button>}>
          {phase.message}
        </Notice>
      )

    case 'start':
      return <Start today={phase.today} onStart={() => setPhase({name: 'playing', today: phase.today, startedAt: Date.now()})} />

    case 'playing':
      return (
        <Play
          today={phase.today}
          startedAt={phase.startedAt}
          onFinish={(state, durationMs) => {
            if (phase.today.mode === 'practice') {
              setPhase({name: 'result', today: phase.today, result: scoreGame(state.sets, state.guesses, durationMs), board: [], variant: 'practice'})
            } else {
              void post(phase.today, allGuesses(state), durationMs)
            }
          }}
        />
      )

    case 'posting':
      if (!phase.error) return <Notice>Posting your score...</Notice>
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
          onOpenMugup={() => openMugup(phase.today.mugupUrl)}
          onPracticeAgain={() => void load()}
        />
      )
  }
}

function Start({today, onStart}: {today: Today; onStart: () => void}) {
  const practice = today.mode === 'practice'
  return (
    <Page>
      <div className="px-0 py-8 text-center sm:py-12">
        <h1 className="mb-1 text-lg font-bold text-white sm:text-2xl">{today.title}</h1>
        {today.subtitle && <p className="mb-4 text-[#98a2b3]">{today.subtitle}</p>}
        <p className="mx-auto mb-[22px] mt-1.5 max-w-[600px] text-[#c9d1dc]">
          {practice ? (
            <>
              There's no daily match in this channel, so this round isn't scored or posted anywhere. Daily matches come with the hadith in channels where a
              server admin has set up HadithBot.
            </>
          ) : (
            <>
              Tap a name, then tap its meaning. You get a point for each name you match without a wrong guess. You have one try today. If two people get the
              same score, the faster time ranks higher.
            </>
          )}
        </p>
        <Button variant="primary" className="px-[22px] py-3 text-base" onClick={onStart}>
          {practice ? 'Start a practice round' : 'Start the timer and play'}
        </Button>
      </div>
    </Page>
  )
}

