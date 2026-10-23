import {useEffect} from 'react'
import type {BoardRow, Today} from './api'
import {celebrate} from './confetti'
import {AnotherGame} from './GameCards'
import {wording, type GameKey} from './games'
import {formatDuration, pairsWithResult, squares, type Pair, type Result as GameResult} from './game'
import {channelLabel} from './Play'
import {Button, Page, Panel, PoweredByMugup} from './ui'

export type ResultVariant = 'posted' | 'alreadyPlayed' | 'practice'

const pairLabel = (p: Pair) => `${p.left}, ${p.right}`
const MEDALS: Record<number, [string, string]> = {1: ['🥇', '1st place'], 2: ['🥈', '2nd place'], 3: ['🥉', '3rd place']}

/** "{one} X." for one pair; "{many}" and a short list for several. */
function PairList({one, many, pairs}: {one: (label: string) => string; many: (n: number) => string; pairs: Pair[]}) {
  if (pairs.length === 0) return null
  if (pairs.length === 1) return <p className="mt-2 text-[#c9d1dc]">{one(pairLabel(pairs[0]))}</p>
  return (
    <div className="mx-auto mt-3 max-w-[560px] text-[#c9d1dc]">
      <p>{many(pairs.length)}</p>
      <ul className="mt-1.5 space-y-0.5 text-sm text-[#aeb7c3]">
        {pairs.map((p) => (
          <li key={p.id}>{pairLabel(p)}</li>
        ))}
      </ul>
    </div>
  )
}

export function Result({
  today,
  result,
  board,
  variant,
  revealed,
  onOpenMugup,
  onOpenMugupDiscord,
  onPracticeAgain,
  onOpenGame,
}: {
  today: Today
  result: GameResult
  board: BoardRow[]
  variant: ResultVariant
  /** Pair ids the player had shown, when this screen follows a run just played. Null when loaded from the server. */
  revealed: number[] | null
  onOpenMugup: () => void
  onOpenMugupDiscord: () => void
  onPracticeAgain: () => void
  onOpenGame: (game: GameKey) => void
}) {
  const w = wording(today.game)
  const fresh = revealed !== null && variant !== 'alreadyPlayed'
  const perfect = result.score === result.total

  useEffect(() => {
    if (!fresh) return
    return celebrate(perfect)
  }, [fresh, perfect])

  const took = formatDuration(result.durationMs)
  const retried = pairsWithResult(today.sets, result.itemResults, false)
  const unmatched = pairsWithResult(today.sets, result.itemResults, null)
  const missedAny = retried.length + unmatched.length > 0
  const shown = revealed ? retried.filter((p) => revealed.includes(p.id)) : []
  const tried = revealed ? retried.filter((p) => !revealed.includes(p.id)) : []

  return (
    <Page label={w.header} place={variant === 'practice' ? 'Practice' : channelLabel(today)}>
      <Panel className="anim-rise px-5 py-7 text-center sm:px-8 sm:py-9">
        {variant === 'alreadyPlayed' && (
          <p className="mx-auto mb-4 w-fit rounded-full border border-[#ffd38a]/30 bg-[#ffd38a]/10 px-3 py-1 text-sm font-semibold text-[#ffd38a]">
            You've already played today.
          </p>
        )}
        <p className="text-[#98a2b3]">You matched</p>
        <h1 className="mt-1 text-white">
          <span className="block text-[44px] font-extrabold leading-none tracking-tight sm:text-[56px]">
            {result.score} of {result.total}
          </span>
          <span className="mt-1 block text-lg font-semibold text-[#dfe5ee] sm:text-xl">on the first try</span>
        </h1>
        {took && <p className="mt-1 text-[#98a2b3]">in {took}</p>}

        <div className="mb-1 mt-4 text-[22px] leading-tight tracking-[2px] sm:text-[26px]" role="img" aria-label={`${result.score} of ${result.total} right on the first try`}>
          {squares(result.itemResults, today.sets).map((row, i) => (
            <div key={i}>{row}</div>
          ))}
        </div>
        <p className="text-xs text-[#7f8a9a]">🟩 right on the first try · 🟥 took more than one try or was shown · ⬜ stopped before matching it</p>

        {revealed ? (
          <>
            <PairList one={(l) => `You took more than one try on ${l}.`} many={(n) => `You took more than one try on these ${n}${w.listNoun}:`} pairs={tried} />
            <PairList one={(l) => `You had the game show you ${l}.`} many={(n) => `You had the game show you these ${n}${w.listNoun}:`} pairs={shown} />
          </>
        ) : (
          <PairList one={(l) => `You didn't get ${l} on the first try.`} many={(n) => `You didn't get these ${n}${w.listNoun} on the first try:`} pairs={retried} />
        )}
        <PairList one={(l) => `You stopped before matching ${l}.`} many={(n) => `You stopped before matching these ${n}${w.listNoun}:`} pairs={unmatched} />

        <p className="mt-4 text-sm text-[#98a2b3]">
          {variant === 'practice'
            ? "This was a practice round, so your score isn't posted anywhere."
            : `Your score is posted in ${channelLabel(today)}.${today.nextMatch ? ` The next match comes with ${today.nextMatch}.` : ''}`}
        </p>

        {variant === 'practice' && (
          <Button variant="primary" className="mt-5 px-[22px] py-3 text-base" onClick={onPracticeAgain}>
            Start another practice round
          </Button>
        )}
      </Panel>

      <AnotherGame today={today} onOpen={onOpenGame} />

      {variant !== 'practice' && board.length > 0 && (
        <Panel className="mt-4 px-4 py-3 sm:px-5">
          <h2 className="mb-1.5 text-[15px] font-bold text-white">{w.boardHeading}</h2>
          <ol>
            {board.map((row) => {
              const time = formatDuration(row.durationMs)
              const medal = MEDALS[row.rank]
              return (
                <li
                  key={`${row.rank}-${row.displayName}`}
                  className={`flex items-center justify-between gap-3 border-t border-[#1f2834] px-2 py-2 text-sm first:border-t-0 ${
                    row.isMe ? 'rounded-lg border-transparent bg-[#ffd38a]/10 font-bold text-[#ffd38a]' : 'text-[#dfe5ee]'
                  }`}>
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="w-6 shrink-0 text-center tabular-nums">
                      {medal ? (
                        <span role="img" aria-label={medal[1]}>
                          {medal[0]}
                        </span>
                      ) : (
                        `${row.rank}.`
                      )}
                    </span>
                    <span className="truncate">{row.isMe ? `You (${row.displayName})` : row.displayName}</span>
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {row.score}/{row.total}
                    {time ? ` · ${time}` : ''}
                  </span>
                </li>
              )
            })}
          </ol>
        </Panel>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3.5 rounded-xl border border-[#4a3a22] bg-[#1a1610] px-4 py-3.5">
        <p className="max-w-[520px] text-sm text-[#e7d6bb]">
          <b>{w.learnHeading}</b> {w.learnText(missedAny)}
        </p>
        <Button variant="gold" onClick={onOpenMugup}>
          {w.learnButton} ↗
        </Button>
      </div>

      <PoweredByMugup onOpen={onOpenMugupDiscord} />
    </Page>
  )
}
