import {useEffect, useRef, useState} from 'react'
import type {Today} from './api'
import {
  advanceSet,
  clearReveal,
  clearWrong,
  currentSet,
  deselect,
  formatClock,
  isBusy,
  isGameOver,
  isMatched,
  isMissed,
  isSetCleared,
  lastEvent,
  mistakeCount,
  parseCardKey,
  pick,
  reveal,
  scoreSet,
  scoreSoFar,
  shuffleCards,
  startGame,
  type GameEvent,
  type GameState,
  type Pair,
  type PairSet,
} from './game'
import {moveCursor, settleCursor, type BoardShape, type Move} from './nav'
import {playSound, unlockAudio, useSoundSetting} from './sound'
import {Button, Kbd, Page, Panel, plural, useFinePointer, useGridColumns, useIsPhone} from './ui'

/** How long a wrong pair stays red before both cards unselect. Same as MugUp. */
const WRONG_MS = 1000
/** How long a pair shown by "Show one pair" stays highlighted. */
const REVEAL_MS = 900
/** A short pause on a cleared set before the next one loads, so the last match is seen. */
const NEXT_SET_MS = 700

const ARROWS: Record<string, Move> = {ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right'}

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

function announcement(event: GameEvent, state: GameState): string {
  const pair = (id: number) => state.sets.flatMap((s) => s.pairs).find((p) => p.id === id)
  const label = (id: number) => {
    const p = pair(id)
    return p ? `${p.left}, ${p.right}` : ''
  }
  switch (event.kind) {
    case 'pick': {
      const card = parseCardKey(state.selected!)
      const p = pair(card.pairId)
      return p ? `Picked ${card.side === 'name' ? p.left : p.right}.` : ''
    }
    case 'match':
      return `Matched: ${label(event.pairId)}.`
    case 'wrong':
      return 'Not a pair. That counts as a mistake.'
    case 'reveal':
      return `Shown: ${label(event.pairId)}. That counts as a mistake.`
    case 'setCleared':
      return 'Set cleared. The next set is loading.'
    case 'finished':
      return 'Every pair is matched.'
  }
}

export function SoundToggle() {
  const [on, toggle] = useSoundSetting()
  return (
    <Button className="px-3 py-1.5 text-xs" aria-pressed={on} onClick={toggle}>
      {on ? 'Sound: on' : 'Sound: off'}
    </Button>
  )
}

export function Play({today, startedAt, onFinish}: {today: Today; startedAt: number; onFinish: (state: GameState, durationMs: number) => void}) {
  const isPhone = useIsPhone()
  const finePointer = useFinePointer()
  const cols = useGridColumns()
  const shape: BoardShape = isPhone ? {kind: 'columns'} : {kind: 'grid', cols}

  const [state, setState] = useState(() => startGame(today.sets))
  const [cursor, setCursor] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [confirming, setConfirming] = useState(false)
  const [announce, setAnnounce] = useState('')

  const finished = useRef(false)
  const prevState = useRef(state)
  const cardRefs = useRef(new Map<string, HTMLButtonElement>())
  /** True after a key press, false after a tap or click: only keyboard players get focus moved for them. */
  const usingKeys = useRef(false)
  // The key handler is attached once and reads the latest values from here.
  const live = useRef({state, cursor, shape, confirming})
  live.current = {state, cursor, shape, confirming}

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
    if (!state.revealing) return
    const id = setTimeout(() => setState(clearReveal), REVEAL_MS)
    return () => clearTimeout(id)
  }, [state.revealing])

  // Sounds and the screen-reader line, from what the last change was.
  useEffect(() => {
    const event = lastEvent(prevState.current, state)
    prevState.current = state
    if (!event) return
    playSound(event.kind, event.kind === 'match' ? event.combo : 0)
    setAnnounce(announcement(event, state))
  }, [state])

  // A cleared set moves on by itself; the last one ends the game. Both wait for a highlight to finish.
  useEffect(() => {
    if (isBusy(state) || !isSetCleared(state)) return
    if (isGameOver(state)) {
      finish(state)
      return
    }
    const id = setTimeout(() => setState((s) => advanceSet(s)), NEXT_SET_MS)
    return () => clearTimeout(id)
    // finish only reads a ref and props that don't change during a game.
  }, [state])

  // When the card under the keyboard cursor gets matched (or a new set loads), move to the nearest open one.
  useEffect(() => {
    if (!usingKeys.current || cursor === null) return
    const settled = settleCursor(state.layout, state.matched[state.setIndex], cursor, shape)
    if (settled !== cursor) setCursor(settled)
  }, [state, cursor, shape])

  useEffect(() => {
    if (usingKeys.current && cursor) cardRefs.current.get(cursor)?.focus()
  }, [cursor])

  useEffect(() => {
    const onPointer = () => {
      usingKeys.current = false
      unlockAudio()
    }
    const onKey = (e: KeyboardEvent) => {
      const {state: s, cursor: c, shape: sh, confirming: dialogOpen} = live.current
      // The stop dialog handles its own keys (Escape keeps playing, Enter presses the focused button).
      if (dialogOpen || e.metaKey || e.ctrlKey || e.altKey) return
      usingKeys.current = true
      unlockAudio()

      const move = ARROWS[e.key]
      if (move) {
        e.preventDefault()
        setCursor(moveCursor(s.layout, s.matched[s.setIndex], c, move, sh))
        return
      }
      if (e.repeat) return
      const key = e.key.toLowerCase()
      if (key === 'escape') {
        setState(deselect)
      } else if (key === 's') {
        setState((st) => shuffleCards(st))
      } else if (key === 'h') {
        setState((st) => reveal(st))
      } else if (key === 'enter' || key === ' ') {
        // On a focused button the browser presses it already. This covers focus being nowhere.
        if (document.activeElement instanceof HTMLButtonElement) return
        const target = settleCursor(s.layout, s.matched[s.setIndex], c, sh)
        if (!target) return
        e.preventDefault()
        setCursor(target)
        setState((st) => pick(st, target))
      }
    }
    window.addEventListener('pointerdown', onPointer)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('keydown', onKey)
    }
  }, [])

  const set = currentSet(state)
  const pairsById = new Map(set.pairs.map((p) => [p.id, p]))
  const matchedHere = state.matched[state.setIndex].length
  const totalPairs = state.sets.reduce((n, s) => n + s.pairs.length, 0)
  const matchedAll = state.matched.reduce((n, m) => n + m.length, 0)
  const mistakes = mistakeCount(state)
  const {score, total} = scoreSoFar(state)
  const daily = today.mode === 'daily'
  const busy = isBusy(state) || isSetCleared(state)
  const tabbable = settleCursor(state.layout, state.matched[state.setIndex], cursor, shape)
  const anyMissedMatch = state.matched[state.setIndex].some((id) => state.missed[state.setIndex].includes(id))

  const card = (key: string) => (
    <CardButton
      key={key}
      ref={(el) => {
        if (el) cardRefs.current.set(key, el)
        else cardRefs.current.delete(key)
      }}
      cardKey={key}
      pair={pairsById.get(parseCardKey(key).pairId)!}
      matched={isMatched(state, key)}
      missed={isMissed(state, key)}
      selected={state.selected === key}
      wrong={state.wrongPair?.includes(key) ?? false}
      revealing={state.revealing?.includes(key) ?? false}
      compact={isPhone}
      tabIndex={key === tabbable ? 0 : -1}
      onFocus={() => setCursor(key)}
      onPick={() => {
        setCursor(key)
        setState((s) => pick(s, key))
      }}
    />
  )

  const controls = (
    <div className={isPhone ? 'mt-4' : 'mb-5'}>
      <div className="flex flex-wrap justify-center gap-2.5">
        <Button onClick={() => setState((s) => shuffleCards(s))} disabled={busy}>
          {isPhone ? 'Shuffle' : 'Shuffle the cards'}
          {finePointer && <Kbd>S</Kbd>}
        </Button>
        <Button variant="reveal" onClick={() => setState((s) => reveal(s))} disabled={busy}>
          {state.selected ? "Show this card's pair (costs 1 mistake)" : 'Show one pair (costs 1 mistake)'}
          {finePointer && <Kbd>H</Kbd>}
        </Button>
        <Button variant="warn" onClick={() => setConfirming(true)}>
          {daily ? 'Stop and post my score' : 'Stop and see my score'}
        </Button>
      </div>
      {finePointer && (
        <p className="mt-2.5 text-center text-xs text-[#7f8a9a]">Keys: arrows to move, Enter to pick, S to shuffle, H to show a pair, Esc to clear.</p>
      )}
    </div>
  )

  const stat = (strong: string, rest: string, key?: number) => (
    <span key={key}>
      <b className="font-semibold text-white">{strong}</b>
      {rest ? ` ${rest}` : ''}
    </span>
  )

  return (
    <Page place={daily ? channelLabel(today) : 'Practice'} headerRight={<SoundToggle />}>
      <h1 className="mb-1 text-lg font-bold tracking-tight text-white sm:text-2xl">{heading(state, isPhone)}</h1>
      {!isPhone && <p className="mb-4 text-[#98a2b3]">{subheading(today, set)}</p>}

      <Panel className={`mb-4 overflow-hidden ${isPhone ? 'mt-3' : ''}`}>
        <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5 text-[#b7c0cc] ${isPhone ? 'text-[13px]' : 'text-sm'}`}>
          {state.sets.length > 1 ? (
            <>
              {state.sets.slice(0, state.setIndex).map((s, i) =>
                stat(`${capitalise(s.kind)}: ${scoreSet(s.pairs, state.guesses[i]).filter((r) => r === true).length} of ${s.pairs.length}`, 'on the first try', i),
              )}
              {stat(`${capitalise(set.kind)}: ${matchedHere} of ${set.pairs.length}`, 'matched')}
            </>
          ) : (
            <>
              {stat(`${matchedHere} of ${set.pairs.length}`, isPhone ? '' : 'matched')}
              {stat(String(mistakes), plural(mistakes, 'mistake', 'mistakes'))}
            </>
          )}
          <span className="rounded-full border border-[#2a3443] bg-black/20 px-2.5 py-[3px] font-mono text-[13px] font-bold tabular-nums text-white">
            <span className="sr-only">Time so far: </span>
            {formatClock(now - startedAt)}
          </span>
        </div>
        <div className="h-1.5 bg-[#1f2834]">
          <div className="h-full bg-ok-line transition-[width] duration-300" style={{width: `${(matchedAll / totalPairs) * 100}%`}} />
        </div>
      </Panel>

      {!isPhone && controls}

      <div role="group" aria-label="Cards">
        {isPhone ? (
          <div className="grid grid-cols-2 gap-2">
            <div className="-mb-0.5 text-center text-xs font-medium uppercase tracking-wide text-[#7f8a9a]">Names</div>
            <div className="-mb-0.5 text-center text-xs font-medium uppercase tracking-wide text-[#7f8a9a]">Meanings</div>
            {state.layout.names.flatMap((nameKey, i) => [card(nameKey), card(state.layout.meanings[i])])}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3 md:grid-cols-5">{state.layout.mixed.map(card)}</div>
        )}
      </div>

      {anyMissedMatch && (
        <p className="mt-3 text-center text-xs text-[#98a2b3]">Green cards are matched. A dashed red border means that pair cost a mistake, so it won't score.</p>
      )}

      {isPhone && controls}

      <p className="mt-6 text-center text-xs text-[#6d7787]">Matching game by MugUp</p>
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

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

type CardProps = {
  ref: (el: HTMLButtonElement | null) => void
  cardKey: string
  pair: Pair
  matched: boolean
  missed: boolean
  selected: boolean
  wrong: boolean
  revealing: boolean
  compact: boolean
  tabIndex: number
  onFocus: () => void
  onPick: () => void
}

function CardButton({ref, cardKey, pair, matched, missed, selected, wrong, revealing, compact, tabIndex, onFocus, onPick}: CardProps) {
  const isName = parseCardKey(cardKey).side === 'name'
  const text = isName ? pair.left : pair.right

  let look: string
  if (revealing) look = 'anim-reveal bg-reveal-bg border-reveal-line text-[#fbe3b5]'
  else if (matched && missed) look = 'anim-pop border-dashed border-[#c0626f] bg-ok-bg text-[#9be3bb] opacity-75'
  else if (matched) look = 'anim-pop bg-ok-bg border-ok-line text-[#9be3bb] opacity-75'
  else if (wrong) look = 'anim-shake bg-bad-bg border-bad-line text-[#ffc9d0]'
  else if (isName) look = 'bg-name-bg border-name-line text-[#f1f4f8] hover:border-[#4a8bd0] hover:bg-[#132741]'
  else look = 'bg-mean-bg border-mean-line text-[#fbe6cf] hover:border-[#e08646] hover:bg-[#2f1f12]'

  const lift = !matched && !wrong && !revealing ? 'hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.97]' : ''
  const ring = selected && !wrong ? '-translate-y-0.5 shadow-[0_0_0_3px_#e8edf5,0_8px_20px_-8px_rgba(0,0,0,.8)]' : ''
  const size = compact ? 'min-h-[52px] p-1.5 text-[13px]' : 'min-h-[84px] px-2.5 py-2 text-[15px]'
  const showArabic = isName && pair.leftAr && !(compact && matched)
  const status = matched ? (missed ? ', matched after a mistake' : ', matched') : wrong ? ', not a pair' : ''

  return (
    <button
      ref={ref}
      type="button"
      onClick={onPick}
      onFocus={onFocus}
      disabled={matched || revealing}
      tabIndex={tabIndex}
      aria-pressed={selected}
      aria-label={`${text}${isName && pair.leftAr ? `, ${pair.leftAr}` : ''} (${isName ? 'name' : 'meaning'})${status}`}
      className={`relative grid cursor-pointer place-items-center rounded-xl border-[1.5px] text-center font-semibold leading-snug transition duration-150 disabled:cursor-default ${size} ${look} ${lift} ${ring}`}>
      <span>
        {text}
        {showArabic && (
          <span lang="ar" dir="rtl" className={`mt-0.5 block font-arabic font-medium ${compact ? 'text-sm' : 'text-[18px]'}`}>
            {pair.leftAr}
          </span>
        )}
      </span>
      {matched && !revealing && (
        <span aria-hidden className={`absolute right-2 top-1 text-[13px] ${missed ? 'text-[#e58a98]' : ''}`}>
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
  const keep = useRef(onKeepPlaying)
  keep.current = onKeepPlaying
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') keep.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="fixed inset-0 z-10 grid place-items-center bg-black/65 p-4 backdrop-blur-[2px]" onClick={onKeepPlaying}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="stop-title"
        aria-describedby="stop-body"
        className="anim-rise w-full max-w-[420px] rounded-xl border border-[#2a3443] bg-game-panel p-5 shadow-[0_24px_60px_-20px_rgba(0,0,0,.9)]"
        onClick={(e) => e.stopPropagation()}>
        <h2 id="stop-title" className="mb-2 text-[17px] font-bold text-white">
          {daily ? `Stop now and post ${score} out of ${total}?` : `Stop now with ${score} out of ${total}?`}
        </h2>
        <p id="stop-body" className="mb-5 text-[#b7c0cc]">
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
