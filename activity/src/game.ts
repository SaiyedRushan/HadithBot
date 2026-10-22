/**
 * The pair match, as pure functions: no React, no fetch, no clock.
 *
 * Ported from MugUp's PairMatchGamePlay.tsx. The rules here must agree with the server's
 * replay of the guess log (name_match.score_guesses in the bot), because the server
 * recomputes the score from `guesses` and ignores anything else the client says:
 *
 *   - A guess is one name card plus one meaning card, logged as [namePairId, meaningPairId].
 *   - Same id: the pair is matched. Different ids: both pairs are marked missed.
 *   - ['reveal', pairId] is the "Show one pair" button: the pair is matched for the player
 *     and marked missed, so it can't score. It's rejected for a pair already matched.
 *   - A pair scores when it was matched and never took part in a mistake (a wrong guess or
 *     a reveal).
 *   - A pair never matched is null (shown as a white square).
 *   - No guess ever involves a card that is already matched.
 */

export type Pair = {id: number; left: string; leftAr?: string | null; right: string}
export type PairSet = {kind: string; title: string; pairs: Pair[]}
export type Side = 'name' | 'meaning'
export type Card = {key: string; side: Side; pairId: number}
/** [name card's pair id, meaning card's pair id], or ['reveal', pair id] for "Show one pair". */
export type Guess = [number, number] | ['reveal', number]
export type ItemResult = boolean | null
export type Result = {score: number; total: number; itemResults: ItemResult[]; durationMs: number | null}
export type Rng = () => number

/** Card positions for one set: the mixed grid, and the two phone columns. */
export type Layout = {mixed: string[]; names: string[]; meanings: string[]}

export type GameState = {
  sets: PairSet[]
  setIndex: number
  layout: Layout
  /** The card key picked first, waiting for its partner. */
  selected: string | null
  /** A wrong pair being shown in red. Picks are ignored until clearWrong runs. */
  wrongPair: [string, string] | null
  /** A pair just shown by "Show one pair", highlighted. Picks are ignored until clearReveal runs. */
  revealing: [string, string] | null
  /** Per set, in the order they were made. */
  guesses: Guess[][]
  /** Per set, pair ids matched so far. */
  matched: number[][]
  /** Per set, pair ids that were part of a mistake (a wrong guess or a reveal). */
  missed: number[][]
}

export const cardKey = (side: Side, pairId: number) => `${side}:${pairId}`

export const isReveal = (g: Guess): g is ['reveal', number] => g[0] === 'reveal'

export function parseCardKey(key: string): Card {
  const [side, id] = key.split(':')
  if ((side !== 'name' && side !== 'meaning') || id === undefined || !/^-?\d+$/.test(id)) {
    throw new Error(`Not a card key: ${key}`)
  }
  return {key, side, pairId: Number(id)}
}

/** Fisher-Yates. MugUp sorted by `Math.random() - 0.5`, which is biased; this isn't. */
export function shuffle<T>(items: readonly T[], rng: Rng = Math.random): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export function buildLayout(set: PairSet, rng: Rng = Math.random): Layout {
  const names = set.pairs.map((p) => cardKey('name', p.id))
  const meanings = set.pairs.map((p) => cardKey('meaning', p.id))
  return {
    mixed: shuffle([...names, ...meanings], rng),
    names: shuffle(names, rng),
    meanings: shuffle(meanings, rng),
  }
}

/** Shuffles only the unmatched cards. Matched cards keep their places. */
export function reshuffleUnmatched(order: readonly string[], matched: readonly number[], rng: Rng = Math.random): string[] {
  const isOpen = (key: string) => !matched.includes(parseCardKey(key).pairId)
  const slots: number[] = []
  order.forEach((key, i) => {
    if (isOpen(key)) slots.push(i)
  })
  const moved = shuffle(
    slots.map((i) => order[i]),
    rng,
  )
  const out = [...order]
  slots.forEach((slot, n) => {
    out[slot] = moved[n]
  })
  return out
}

export function startGame(sets: PairSet[], rng: Rng = Math.random): GameState {
  if (sets.length === 0 || sets.some((s) => s.pairs.length === 0)) throw new Error('A match needs at least one set with pairs in it')
  return {
    sets,
    setIndex: 0,
    layout: buildLayout(sets[0], rng),
    selected: null,
    wrongPair: null,
    revealing: null,
    guesses: sets.map(() => []),
    matched: sets.map(() => []),
    missed: sets.map(() => []),
  }
}

const replaceAt = <T>(list: readonly T[], index: number, value: T): T[] => list.map((v, i) => (i === index ? value : v))

export function currentSet(state: GameState): PairSet {
  return state.sets[state.setIndex]
}

export function isMatched(state: GameState, key: string): boolean {
  return state.matched[state.setIndex].includes(parseCardKey(key).pairId)
}

/** True when the card's pair was part of a mistake in this set. */
export function isMissed(state: GameState, key: string): boolean {
  return state.missed[state.setIndex].includes(parseCardKey(key).pairId)
}

/** Waiting on the red display of a wrong pair or the highlight of a shown pair. */
export const isBusy = (state: GameState) => state.wrongPair !== null || state.revealing !== null

export function isSetCleared(state: GameState): boolean {
  return state.matched[state.setIndex].length === currentSet(state).pairs.length
}

export function isGameOver(state: GameState): boolean {
  return state.setIndex === state.sets.length - 1 && isSetCleared(state)
}

/**
 * One tap on a card.
 *
 * - Ignored while a wrong pair is showing, on a matched card, or once the set is cleared.
 * - Nothing selected: select it. The selected card again: deselect it.
 * - A second card of the same type: it replaces the selection, and no guess is logged.
 * - A card of the other type: that's a guess, logged as [name id, meaning id].
 */
export function pick(state: GameState, key: string): GameState {
  if (isBusy(state) || isSetCleared(state) || isMatched(state, key)) return state
  const card = parseCardKey(key)
  const i = state.setIndex
  if (!currentSet(state).pairs.some((p) => p.id === card.pairId)) return state

  if (state.selected === null) return {...state, selected: key}
  if (state.selected === key) return {...state, selected: null}

  const first = parseCardKey(state.selected)
  if (first.side === card.side) return {...state, selected: key}

  const name = first.side === 'name' ? first : card
  const meaning = first.side === 'name' ? card : first
  const guesses = replaceAt(state.guesses, i, [...state.guesses[i], [name.pairId, meaning.pairId] as Guess])

  if (name.pairId === meaning.pairId) {
    return {...state, guesses, selected: null, matched: replaceAt(state.matched, i, [...state.matched[i], name.pairId])}
  }

  const missed = new Set(state.missed[i])
  missed.add(name.pairId)
  missed.add(meaning.pairId)
  return {...state, guesses, selected: null, wrongPair: [state.selected, key], missed: replaceAt(state.missed, i, [...missed])}
}

/** Clears the selection (the Escape key). */
export function deselect(state: GameState): GameState {
  return state.selected === null ? state : {...state, selected: null}
}

/** Ends the red display of a wrong pair (the UI calls this after 1 second). */
export function clearWrong(state: GameState): GameState {
  return state.wrongPair ? {...state, wrongPair: null} : state
}

/** The pair "Show one pair" would show: the selected card's pair, else null (a random one). */
export function revealTarget(state: GameState): number | null {
  return state.selected === null ? null : parseCardKey(state.selected).pairId
}

/**
 * "Show one pair (costs 1 mistake)". Shows the selected card's pair, or a random unmatched
 * pair when nothing is selected. The pair is matched and marked missed, and the log gets
 * ['reveal', pairId].
 */
export function reveal(state: GameState, rng: Rng = Math.random): GameState {
  if (isBusy(state) || isSetCleared(state)) return state
  const i = state.setIndex
  const open = currentSet(state).pairs.filter((p) => !state.matched[i].includes(p.id))
  const target = revealTarget(state) ?? open[Math.floor(rng() * open.length)]?.id
  if (target === undefined || state.matched[i].includes(target)) return state
  const missed = state.missed[i].includes(target) ? state.missed[i] : [...state.missed[i], target]
  return {
    ...state,
    selected: null,
    revealing: [cardKey('name', target), cardKey('meaning', target)],
    guesses: replaceAt(state.guesses, i, [...state.guesses[i], ['reveal', target] as Guess]),
    matched: replaceAt(state.matched, i, [...state.matched[i], target]),
    missed: replaceAt(state.missed, i, missed),
  }
}

/** Ends the highlight of a shown pair (the UI calls this after about 900 ms). */
export function clearReveal(state: GameState): GameState {
  return state.revealing ? {...state, revealing: null} : state
}

/** Moves to the next set once the current one is cleared. A no-op otherwise. */
export function advanceSet(state: GameState, rng: Rng = Math.random): GameState {
  if (!isSetCleared(state) || state.setIndex >= state.sets.length - 1) return state
  const setIndex = state.setIndex + 1
  return {...state, setIndex, layout: buildLayout(state.sets[setIndex], rng), selected: null, wrongPair: null, revealing: null}
}

/** "Shuffle the cards": new positions for the unmatched cards, and the selection cleared. */
export function shuffleCards(state: GameState, rng: Rng = Math.random): GameState {
  if (isBusy(state)) return state
  const matched = state.matched[state.setIndex]
  return {
    ...state,
    selected: null,
    layout: {
      mixed: reshuffleUnmatched(state.layout.mixed, matched, rng),
      names: reshuffleUnmatched(state.layout.names, matched, rng),
      meanings: reshuffleUnmatched(state.layout.meanings, matched, rng),
    },
  }
}

/** Every guess, in order, across all sets: the `guesses` field of POST /api/result. */
export function allGuesses(state: GameState): Guess[] {
  return state.guesses.flat()
}

/** Wrong guesses plus pairs shown by "Show one pair": the "N mistakes" counter. */
export function mistakeCount(state: GameState): number {
  return allGuesses(state).filter((g) => isReveal(g) || g[0] !== g[1]).length
}

/**
 * Replays one set's guess log the way the server does. Throws on a log the server would
 * reject (an unknown id, or a card used after it was matched).
 */
export function scoreSet(pairs: readonly Pair[], guesses: readonly Guess[]): ItemResult[] {
  const ids = new Set(pairs.map((p) => p.id))
  const matched = new Set<number>()
  const missed = new Set<number>()
  for (const guess of guesses) {
    if (isReveal(guess)) {
      const id = guess[1]
      if (!ids.has(id)) throw new Error(`Reveal of ${id} names a pair that isn't in this set`)
      if (matched.has(id)) throw new Error(`Reveal of ${id} is for a pair already matched`)
      matched.add(id)
      missed.add(id)
      continue
    }
    const [n, m] = guess
    if (!ids.has(n) || !ids.has(m)) throw new Error(`Guess [${n}, ${m}] names a card that isn't in this set`)
    if (matched.has(n) || matched.has(m)) throw new Error(`Guess [${n}, ${m}] uses a card that was already matched`)
    if (n === m) {
      matched.add(n)
    } else {
      missed.add(n)
      missed.add(m)
    }
  }
  return pairs.map((p) => (matched.has(p.id) ? !missed.has(p.id) : null))
}

/** The result for the whole match, with itemResults flattened in set order then pair order. */
export function scoreGame(sets: readonly PairSet[], guessesPerSet: readonly (readonly Guess[])[], durationMs: number | null): Result {
  const itemResults = sets.flatMap((set, i) => scoreSet(set.pairs, guessesPerSet[i] ?? []))
  return {
    score: itemResults.filter((r) => r === true).length,
    total: itemResults.length,
    itemResults,
    durationMs,
  }
}

/** The score the player would post if they stopped right now. */
export function scoreSoFar(state: GameState): {score: number; total: number} {
  const {score, total} = scoreGame(state.sets, state.guesses, null)
  return {score, total}
}

/** `48s`, `1m 05s`, `1h 03m`. Empty for a missing or non-positive time. Port of MugUp's score-grid.ts. */
export function formatDuration(ms: number | null | undefined): string {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms <= 0) return ''
  const totalSeconds = Math.max(1, Math.round(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`
  if (minutes > 0) return `${minutes}m ${String(seconds).padStart(2, '0')}s`
  return `${seconds}s`
}

/** The running timer: `00:42`, `12:05`. Minutes keep counting past 59. */
export function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

const SQUARE = {right: '🟩', retried: '🟥', unmatched: '⬜'}

/** One row of squares per set, the same as the Discord message shows. */
export function squares(itemResults: readonly ItemResult[], sets: readonly PairSet[]): string[] {
  const rows: string[] = []
  let start = 0
  for (const set of sets) {
    const row = itemResults.slice(start, start + set.pairs.length)
    rows.push(row.map((r) => (r === true ? SQUARE.right : r === false ? SQUARE.retried : SQUARE.unmatched)).join(''))
    start += set.pairs.length
  }
  return rows
}

/** The pairs whose result is `want` (false: took more than one try; null: never matched). */
export function pairsWithResult(sets: readonly PairSet[], itemResults: readonly ItemResult[], want: false | null): Pair[] {
  const pairs = sets.flatMap((s) => s.pairs)
  return pairs.filter((_, i) => itemResults[i] === want)
}

/** Pair ids the player had shown with "Show one pair", across all sets. */
export function revealedIds(guessesPerSet: readonly (readonly Guess[])[]): number[] {
  return guessesPerSet.flatMap((gs) => gs.filter(isReveal).map((g) => g[1]))
}

export type GameEvent =
  | {kind: 'pick'}
  | {kind: 'match'; pairId: number; combo: number}
  | {kind: 'wrong'; pairIds: [number, number]}
  | {kind: 'reveal'; pairId: number}
  | {kind: 'setCleared'}
  | {kind: 'finished'}

/**
 * What one state change was, for sounds and the screen-reader announcement. `combo` counts
 * the matches in a row at the end of this set's log, so a streak can climb in pitch.
 */
export function lastEvent(prev: GameState, next: GameState): GameEvent | null {
  if (prev === next) return null
  const grew = next.guesses[next.setIndex].length > (prev.setIndex === next.setIndex ? prev.guesses[prev.setIndex].length : 0)
  if (grew) {
    if (isGameOver(next)) return {kind: 'finished'}
    if (isSetCleared(next)) return {kind: 'setCleared'}
    const log = next.guesses[next.setIndex]
    const g = log[log.length - 1]
    if (isReveal(g)) return {kind: 'reveal', pairId: g[1]}
    if (g[0] !== g[1]) return {kind: 'wrong', pairIds: [g[0], g[1]]}
    let combo = 0
    for (let k = log.length - 1; k >= 0 && !isReveal(log[k]) && log[k][0] === log[k][1]; k--) combo++
    return {kind: 'match', pairId: g[0], combo}
  }
  if (next.selected !== null && next.selected !== prev.selected) return {kind: 'pick'}
  return null
}
