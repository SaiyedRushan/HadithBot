import {useEffect, useRef, useState} from 'react'
import type {Today} from './api'
import {
  advanceSet,
  clearWrong,
  currentSet,
  formatClock,
  isGameOver,
  isMatched,
  isSetCleared,
  parseCardKey,
  pick,
  scoreSet,
  scoreSoFar,
  shuffleCards,
  startGame,
  wrongGuessCount,
  type GameState,
  type Pair,
  type PairSet,
} from './game'
import {Button, Page, plural, useIsPhone} from './ui'

/** How long a wrong pair stays red before both cards unselect. Same as MugUp. */
const WRONG_MS = 1000
/** A short pause on a cleared set before the next one loads, so the last match is seen. */
const NEXT_SET_MS = 700

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

export function channelLabel(today: Today) {
  return today.channelName ? `#${today.channelName}` : 'this channel'
}

function heading(state: GameState, isPhone: boolean) {
  const set = currentSet(state)
  if (state.sets.length > 1) return `Set ${state.setIndex + 1} of ${state.sets.length}: ${lowerFirst(set.title)}`
  if (isPhone && set.kind === 'names') return 'Match each name to its meaning'
  return set.title
}

function subheading(today: Today, set: PairSet) {
  if (today.mode === 'practice') return 'Practice round · nothing is posted'
  if (set.kind === 'names') return `Names ${set.pairs[0].id} to ${set.pairs[set.pairs.length - 1].id} · one try today`
  return 'One try today'
}

export function Play({today, startedAt, onFinish}: {today: Today; startedAt: number; onFinish: (state: GameState, durationMs: number) => void}) {
  const isPhone = useIsPhone()
  const [state, setState] = useState(() => startGame(today.sets))
  const [now, setNow] = useState(() => Date.now())
  const [confirming, setConfirming] = useState(false)
  const finished = useRef(false)

  const finish = (s: GameState) => {
    if (finished.current) return
    finished.current = true
    onFinish(s, Math.max(1, Date.now() - startedAt))
  }

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!state.wrongPair) return
    const id = setTimeout(() => setState(clearWrong), WRONG_MS)
    return () => clearTimeout(id)
  }, [state.wrongPair])

  useEffect(() => {
    if (isGameOver(state)) {
      finish(state)
      return
    }
    if (!isSetCleared(state)) return
    const id = setTimeout(() => setState((s) => advanceSet(s)), NEXT_SET_MS)
    return () => clearTimeout(id)
    // finish only reads a ref and props that don't change during a game.
  }, [state])

  const set = currentSet(state)
  const pairsById = new Map(set.pairs.map((p) => [p.id, p]))
  const matchedHere = state.matched[state.setIndex].length
  const totalPairs = state.sets.reduce((n, s) => n + s.pairs.length, 0)
  const matchedAll = state.matched.reduce((n, m) => n + m.length, 0)
  const wrong = wrongGuessCount(state)
  const {score, total} = scoreSoFar(state)
  const daily = today.mode === 'daily'

  const card = (key: string) => (
    <CardButton
      key={key}
      cardKey={key}
      pair={pairsById.get(parseCardKey(key).pairId)!}
      matched={isMatched(state, key)}
      selected={state.selected === key}
      wrong={state.wrongPair?.includes(key) ?? false}
      compact={isPhone}
      onPick={() => setState((s) => pick(s, key))}
    />
  )

  const controls = (
    <div className={`flex flex-wrap justify-center gap-2.5 ${isPhone ? 'mt-3' : 'mb-4'}`}>
      <Button onClick={() => setState((s) => shuffleCards(s))}>{isPhone ? 'Shuffle' : 'Shuffle the cards'}</Button>
      <Button variant="warn" onClick={() => setConfirming(true)}>
        {daily ? 'Stop and post my score' : 'Stop and see my score'}
      </Button>
    </div>
  )

  return (
    <Page>
      <h1 className="mb-1 text-lg font-bold text-white sm:text-2xl">{heading(state, isPhone)}</h1>
      {!isPhone && <p className="mb-4 text-[#98a2b3]">{subheading(today, set)}</p>}

      <div className={`mb-2.5 flex items-center justify-between gap-3 rounded-[10px] bg-game-panel px-3.5 py-2.5 text-[#b7c0cc] ${isPhone ? 'text-[13px]' : 'text-sm'}`}>
        {state.sets.length > 1 ? (
          <>
            {state.sets.slice(0, state.setIndex).map((s, i) => (
              <span key={i}>
                <b className="text-white">
                  {capitalise(s.kind)}: {scoreSet(s.pairs, state.guesses[i]).filter((r) => r === true).length} of {s.pairs.length}
                </b>{' '}
                on the first try
              </span>
            ))}
            <span>
              <b className="text-white">
                {capitalise(set.kind)}: {matchedHere} of {set.pairs.length}
              </b>{' '}
              matched
            </span>
          </>
        ) : isPhone ? (
          <>
            <span>
              <b className="text-white">
                {matchedHere} of {set.pairs.length}
              </b>
            </span>
            <span>
              <b className="text-white">{wrong}</b> wrong
            </span>
          </>
        ) : (
          <>
            <span>
              <b className="text-white">
                {matchedHere} of {set.pairs.length}
              </b>{' '}
              matched
            </span>
            <span>
              <b className="text-white">{wrong}</b> {plural(wrong, 'wrong guess', 'wrong guesses')}
            </span>
          </>
        )}
        <span className="rounded-full border border-[#2a3443] px-2.5 py-[3px] font-mono font-bold text-white" aria-label="Time so far">
          {formatClock(now - startedAt)}
        </span>
      </div>

      <div className="mb-3.5 h-1.5 overflow-hidden rounded-md bg-[#1f2834]">
        <div className="h-full bg-ok-line transition-[width] duration-300" style={{width: `${(matchedAll / totalPairs) * 100}%`}} />
      </div>

      {!isPhone && controls}

      {isPhone ? (
        <div className="grid grid-cols-2 gap-2">
          <div className="-mb-0.5 text-center text-xs text-[#7f8a9a]">Names</div>
          <div className="-mb-0.5 text-center text-xs text-[#7f8a9a]">Meanings</div>
          {state.layout.names.flatMap((nameKey, i) => [card(nameKey), card(state.layout.meanings[i])])}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3 md:grid-cols-5">{state.layout.mixed.map(card)}</div>
      )}

      {isPhone && controls}

      <p className="mt-[18px] text-center text-xs text-[#6d7787]">Matching game by MugUp</p>

      {confirming && (
        <StopDialog
          daily={daily}
          channel={channelLabel(today)}
          score={score}
          total={total}
          onKeepPlaying={() => setConfirming(false)}
          onStop={() => {
            setConfirming(false)
            finish(state)
          }}
        />
      )}
    </Page>
  )
}

function CardButton({
  cardKey,
  pair,
  matched,
  selected,
  wrong,
  compact,
  onPick,
}: {
  cardKey: string
  pair: Pair
  matched: boolean
  selected: boolean
  wrong: boolean
  compact: boolean
  onPick: () => void
}) {
  const isName = parseCardKey(cardKey).side === 'name'
  const look = matched
    ? 'bg-ok-bg border-ok-line text-[#9be3bb] opacity-70'
    : wrong
      ? 'bg-bad-bg border-bad-line text-[#ffc9d0]'
      : isName
        ? 'bg-name-bg border-name-line text-[#f1f4f8] hover:brightness-125'
        : 'bg-mean-bg border-mean-line text-[#fbe6cf] hover:brightness-125'
  const size = compact ? 'min-h-[52px] p-1.5 text-[13px]' : 'min-h-[78px] px-2.5 py-2 text-[15px]'
  const showArabic = isName && pair.leftAr && !(compact && matched)

  return (
    <button
      type="button"
      onClick={onPick}
      disabled={matched}
      aria-pressed={selected}
      className={`relative grid cursor-pointer place-items-center rounded-[10px] border-[1.5px] text-center font-semibold leading-snug transition disabled:cursor-default ${size} ${look} ${
        selected && !wrong ? 'shadow-[0_0_0_3px_#e8edf5]' : ''
      }`}>
      <span>
        {isName ? pair.left : pair.right}
        {showArabic && (
          <span lang="ar" dir="rtl" className={`mt-0.5 block font-arabic font-medium ${compact ? 'text-sm' : 'text-[17px]'}`}>
            {pair.leftAr}
          </span>
        )}
      </span>
      {matched && (
        <span aria-label="Matched" className="absolute right-2 top-1 text-[13px]">
          ✓
        </span>
      )}
    </button>
  )
}

function StopDialog({
  daily,
  channel,
  score,
  total,
  onKeepPlaying,
  onStop,
}: {
  daily: boolean
  channel: string
  score: number
  total: number
  onKeepPlaying: () => void
  onStop: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onKeepPlaying()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onKeepPlaying])

  return (
    <div className="fixed inset-0 z-10 grid place-items-center bg-black/60 p-4" onClick={onKeepPlaying}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="stop-title"
        className="w-full max-w-[420px] rounded-xl border border-[#2a3443] bg-game-panel p-5"
        onClick={(e) => e.stopPropagation()}>
        <h2 id="stop-title" className="mb-2 text-[17px] font-bold text-white">
          {daily ? `Stop now and post ${score} out of ${total}?` : `Stop now with ${score} out of ${total}?`}
        </h2>
        <p className="mb-4 text-[#b7c0cc]">
          {daily
            ? `Your score goes on the board in ${channel} as it is now. You can't play this match again today.`
            : 'This practice round ends here. Nothing is posted anywhere.'}
        </p>
        <div className="flex flex-wrap justify-end gap-2.5">
          <Button autoFocus onClick={onKeepPlaying}>
            Keep playing
          </Button>
          <Button variant="warn" onClick={onStop}>
            {daily ? `Stop and post ${score}/${total}` : `Stop at ${score}/${total}`}
          </Button>
        </div>
      </div>
    </div>
  )
}
