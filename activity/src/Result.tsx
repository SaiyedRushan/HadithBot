import type {BoardRow, Today} from './api'
import {formatDuration, pairsWithResult, squares, type Pair, type Result as GameResult} from './game'
import {channelLabel} from './Play'
import {Button, Page} from './ui'

export type ResultVariant = 'posted' | 'alreadyPlayed' | 'practice'

const pairLabel = (p: Pair) => `${p.left}, ${p.right}`

/** "You took more than one try on X." for one pair; a short list for several. */
function PairList({one, many, pairs}: {one: string; many: (n: number) => string; pairs: Pair[]}) {
  if (pairs.length === 0) return null
  if (pairs.length === 1) {
    return (
      <p className="mt-1 text-[#c9d1dc]">
        {one} {pairLabel(pairs[0])}.
      </p>
    )
  }
  return (
    <div className="mx-auto mt-2 max-w-[560px] text-[#c9d1dc]">
      <p>{many(pairs.length)}</p>
      <ul className="mt-1 space-y-0.5 text-sm">
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
  onOpenMugup,
  onPracticeAgain,
}: {
  today: Today
  result: GameResult
  board: BoardRow[]
  variant: ResultVariant
  onOpenMugup: () => void
  onPracticeAgain: () => void
}) {
  const took = formatDuration(result.durationMs)
  const retried = pairsWithResult(today.sets, result.itemResults, false)
  const unmatched = pairsWithResult(today.sets, result.itemResults, null)
  const missedAny = retried.length + unmatched.length > 0

  return (
    <Page>
      <div className="text-center">
        {variant === 'alreadyPlayed' && <p className="mb-3 font-semibold text-[#ffd38a]">You've already played today.</p>}
        <p className="text-[#98a2b3]">You matched</p>
        <p className="mb-0.5 mt-1.5 text-[28px] font-extrabold leading-tight text-white sm:text-[40px]">
          {result.score} of {result.total} on the first try
        </p>
        {took && <p className="text-[#98a2b3]">in {took}</p>}

        <div className="mb-1 mt-2 text-[22px] tracking-[2px]" aria-label={`${result.score} of ${result.total} on the first try`}>
          {squares(result.itemResults, today.sets).map((row, i) => (
            <div key={i}>{row}</div>
          ))}
        </div>
        <p className="text-xs text-[#7f8a9a]">🟩 right on the first try · 🟥 took more than one try · ⬜ stopped before matching it</p>

        <PairList one="You took more than one try on" many={(n) => `You took more than one try on these ${n}:`} pairs={retried} />
        <PairList one="You stopped before matching" many={(n) => `You stopped before matching these ${n}:`} pairs={unmatched} />

        {variant === 'practice' ? (
          <p className="mt-1 text-[#98a2b3]">This was a practice round, so your score isn't posted anywhere.</p>
        ) : (
          <p className="mt-1 text-[#98a2b3]">
            Your score is posted in {channelLabel(today)}.{today.nextMatch ? ` The next match comes with ${today.nextMatch}.` : ''}
          </p>
        )}

        {variant !== 'practice' && board.length > 0 && (
          <div className="mt-[18px] rounded-[10px] bg-game-panel px-4 py-3 text-left">
            <h2 className="mb-2 text-[15px] font-bold text-white">Today in this server</h2>
            {board.map((row) => {
              const time = formatDuration(row.durationMs)
              const tone = row.isMe ? 'font-bold text-[#ffd38a]' : ''
              return (
                <div key={`${row.rank}-${row.displayName}`} className="flex justify-between gap-3 border-t border-[#1f2834] py-1.5 text-sm first-of-type:border-t-0">
                  <span className={tone}>
                    {row.rank}. {row.isMe ? `You (${row.displayName})` : row.displayName}
                  </span>
                  <span className={`shrink-0 ${tone}`}>
                    {row.score}/{row.total}
                    {time ? ` · ${time}` : ''}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3.5 rounded-[10px] border border-[#4a3a22] bg-[#1a1610] px-4 py-3.5 text-left">
          <p className="max-w-[520px] text-sm text-[#e7d6bb]">
            <b>Want to learn all 99?</b> MugUp has every name as a matching game and flashcards
            {missedAny ? ', so you can practise the ones you missed.' : '.'}
          </p>
          <Button variant="gold" onClick={onOpenMugup}>
            Open the 99 names on MugUp ↗
          </Button>
        </div>

        {variant === 'practice' && (
          <div className="mt-6">
            <Button variant="primary" className="px-[22px] py-3 text-base" onClick={onPracticeAgain}>
              Start another practice round
            </Button>
          </div>
        )}
      </div>
    </Page>
  )
}
