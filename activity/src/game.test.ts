import {describe, expect, it} from 'vitest'
import {
  advanceSet,
  allGuesses,
  buildLayout,
  cardKey,
  clearWrong,
  formatClock,
  formatDuration,
  isGameOver,
  isSetCleared,
  pairsWithResult,
  pick,
  reshuffleUnmatched,
  scoreGame,
  scoreSet,
  scoreSoFar,
  shuffleCards,
  squares,
  startGame,
  mistakeCount,
  reveal,
  clearReveal,
  deselect,
  lastEvent,
  revealedIds,
  isMissed,
  type GameState,
  type PairSet,
} from './game'

const makeSet = (kind: string, ids: number[]): PairSet => ({
  kind,
  title: `Match each ${kind}`,
  pairs: ids.map((id) => ({id, left: `${id}. Left`, leftAr: null, right: `Meaning ${id}`})),
})

const names = makeSet('names', [49, 50, 51, 52, 53, 54, 55, 56, 57, 58])
const N = (id: number) => cardKey('name', id)
const M = (id: number) => cardKey('meaning', id)

/** A fixed sequence, so layouts are reproducible. */
function seeded(seed = 1) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

const tap = (state: GameState, ...keys: string[]) => keys.reduce((s, k) => clearWrong(pick(s, k)), state)

describe('buildLayout', () => {
  it('puts all 20 cards in the mixed grid and 10 in each phone column', () => {
    const layout = buildLayout(names, seeded())
    expect(layout.mixed).toHaveLength(20)
    expect(new Set(layout.mixed).size).toBe(20)
    expect([...layout.names].sort()).toEqual(names.pairs.map((p) => N(p.id)).sort())
    expect([...layout.meanings].sort()).toEqual(names.pairs.map((p) => M(p.id)).sort())
  })
})

describe('a clean run', () => {
  it('scores every pair and logs one guess per pair', () => {
    let s = startGame([names], seeded())
    for (const p of names.pairs) s = tap(s, N(p.id), M(p.id))
    expect(isGameOver(s)).toBe(true)
    expect(allGuesses(s)).toEqual(names.pairs.map((p) => [p.id, p.id]))
    expect(mistakeCount(s)).toBe(0)
    const result = scoreGame(s.sets, s.guesses, 48000)
    expect(result).toEqual({score: 10, total: 10, itemResults: Array(10).fill(true), durationMs: 48000})
    expect(squares(result.itemResults, s.sets)).toEqual(['🟩'.repeat(10)])
  })

  it('logs [name, meaning] even when the meaning is tapped first', () => {
    const s = tap(startGame([names]), M(52), N(52))
    expect(allGuesses(s)).toEqual([[52, 52]])
  })
})

describe('a wrong guess', () => {
  it('marks both pairs as missed, even after they are matched', () => {
    let s = startGame([names])
    s = pick(s, N(52))
    s = pick(s, M(53))
    expect(s.wrongPair).toEqual([N(52), M(53)])
    expect(s.selected).toBeNull()
    s = clearWrong(s)
    s = tap(s, N(52), M(52), N(53), M(53))
    expect(allGuesses(s)).toEqual([
      [52, 53],
      [52, 52],
      [53, 53],
    ])
    const r = scoreGame(s.sets, s.guesses, null)
    expect(r.itemResults.slice(3, 5)).toEqual([false, false])
    expect(r.itemResults[0]).toBeNull()
    expect(r.score).toBe(0)
    expect(mistakeCount(s)).toBe(1)
  })

  it('ignores taps while the wrong pair is showing', () => {
    let s = pick(pick(startGame([names]), N(52)), M(53))
    const during = pick(s, N(49))
    expect(during).toBe(s)
    s = pick(clearWrong(s), N(49))
    expect(s.selected).toBe(N(49))
  })
})

describe('matched cards', () => {
  it('cannot be picked or guessed again', () => {
    let s = tap(startGame([names]), N(50), M(50))
    const before = s
    s = pick(s, N(50))
    expect(s).toBe(before)
    s = pick(s, M(51))
    s = pick(s, N(50))
    expect(s.selected).toBe(M(51))
    expect(allGuesses(s)).toEqual([[50, 50]])
  })

  it('makes the server-side replay reject a log that reuses one', () => {
    expect(() => scoreSet(names.pairs, [[50, 50], [50, 51]])).toThrow(/already matched/)
    expect(() => scoreSet(names.pairs, [[1, 50]])).toThrow(/isn't in this set/)
  })
})

describe('selection', () => {
  it('replaces the selection when the second card is the same type, with no guess', () => {
    let s = pick(startGame([names]), N(49))
    s = pick(s, N(50))
    expect(s.selected).toBe(N(50))
    s = pick(s, M(51))
    s = pick(s, M(52))
    expect(allGuesses(s)).toEqual([[50, 51]])
  })

  it('deselects when the selected card is tapped again', () => {
    let s = pick(startGame([names]), M(49))
    s = pick(s, M(49))
    expect(s.selected).toBeNull()
    expect(allGuesses(s)).toEqual([])
  })
})

describe('stopping early', () => {
  it('leaves unmatched pairs null, even one that was in a wrong guess, and counts only first-try matches', () => {
    let s = startGame([names])
    s = tap(s, N(49), M(49), N(50), M(51), N(50), M(50))
    expect(scoreSoFar(s)).toEqual({score: 1, total: 10})
    const r = scoreGame(s.sets, s.guesses, 40000)
    expect(squares(r.itemResults, s.sets)).toEqual(['🟩🟥⬜⬜⬜⬜⬜⬜⬜⬜'])
    expect(pairsWithResult(s.sets, r.itemResults, false).map((p) => p.id)).toEqual([50])
    expect(pairsWithResult(s.sets, r.itemResults, null).map((p) => p.id)).toEqual([51, 52, 53, 54, 55, 56, 57, 58])
  })
})

describe('shuffle', () => {
  it('keeps matched cards in place and clears the selection', () => {
    let s = tap(startGame([names], seeded(3)), N(49), M(49), N(55), M(55))
    s = pick(s, N(50))
    const before = s.layout
    s = shuffleCards(s, seeded(7))
    expect(s.selected).toBeNull()
    for (const key of [N(49), M(49), N(55), M(55)]) {
      expect(s.layout.mixed.indexOf(key)).toBe(before.mixed.indexOf(key))
    }
    expect([...s.layout.mixed].sort()).toEqual([...before.mixed].sort())
  })

  it('reshuffleUnmatched moves only the open cards', () => {
    const order = [N(1), M(1), N(2), M(2), N(3), M(3)]
    const out = reshuffleUnmatched(order, [2], seeded(5))
    expect(out[2]).toBe(N(2))
    expect(out[3]).toBe(M(2))
    expect([...out].sort()).toEqual([...order].sort())
  })
})

describe('two sets', () => {
  const surahs = makeSet('surahs', [11, 16, 44])
  const small = makeSet('names', [1, 2])

  it('moves to the next set only once the first is cleared', () => {
    let s = startGame([small, surahs])
    s = tap(s, N(1), M(1))
    expect(advanceSet(s)).toBe(s)
    s = tap(s, N(2), M(2))
    expect(isSetCleared(s)).toBe(true)
    expect(isGameOver(s)).toBe(false)
    expect(pick(s, N(1))).toBe(s)
    s = advanceSet(s)
    expect(s.setIndex).toBe(1)
    expect(s.layout.mixed).toHaveLength(6)
  })

  it('flattens itemResults in set order and draws one row of squares per set', () => {
    let s = startGame([small, surahs])
    s = tap(s, N(1), M(2), N(1), M(1), N(2), M(2))
    s = advanceSet(s)
    s = tap(s, N(11), M(11), N(16), M(16))
    expect(allGuesses(s)).toEqual([
      [1, 2],
      [1, 1],
      [2, 2],
      [11, 11],
      [16, 16],
    ])
    const r = scoreGame(s.sets, s.guesses, 70000)
    expect(r.itemResults).toEqual([false, false, true, true, null])
    expect(r.score).toBe(2)
    expect(r.total).toBe(5)
    expect(squares(r.itemResults, s.sets)).toEqual(['🟥🟥', '🟩🟩⬜'])
  })

  it('ends the game when the last pair of the last set is matched', () => {
    let s = startGame([small, surahs])
    s = advanceSet(tap(s, N(1), M(1), N(2), M(2)))
    s = tap(s, N(11), M(11), N(16), M(16), N(44), M(44))
    expect(isGameOver(s)).toBe(true)
    expect(scoreSoFar(s)).toEqual({score: 5, total: 5})
  })
})

describe('formatDuration', () => {
  it('matches the bot and MugUp formats', () => {
    expect(formatDuration(48000)).toBe('48s')
    expect(formatDuration(65000)).toBe('1m 05s')
    expect(formatDuration(3780000)).toBe('1h 03m')
    expect(formatDuration(400)).toBe('1s')
    expect(formatDuration(0)).toBe('')
    expect(formatDuration(null)).toBe('')
  })
})

describe('formatClock', () => {
  it('shows mm:ss', () => {
    expect(formatClock(0)).toBe('00:00')
    expect(formatClock(42900)).toBe('00:42')
    expect(formatClock(65000)).toBe('01:05')
    expect(formatClock(3725000)).toBe('62:05')
  })
})

describe('show one pair (reveal)', () => {
  it("shows the selected card's pair, matched but missed, and logs ['reveal', id]", () => {
    let s = pick(startGame([names]), M(52))
    s = reveal(s)
    expect(s.revealing).toEqual([N(52), M(52)])
    expect(s.selected).toBeNull()
    expect(isMissed(s, N(52))).toBe(true)
    expect(allGuesses(s)).toEqual([['reveal', 52]])
    expect(mistakeCount(s)).toBe(1)
    const r = scoreGame(s.sets, s.guesses, null)
    expect(r.itemResults[3]).toBe(false)
    expect(r.score).toBe(0)
  })

  it('shows a random unmatched pair when nothing is selected', () => {
    let s = tap(startGame([names]), N(49), M(49))
    s = clearReveal(reveal(s, () => 0))
    expect(allGuesses(s)).toEqual([
      [49, 49],
      ['reveal', 50],
    ])
    s = clearReveal(reveal(s, () => 0.99))
    expect(allGuesses(s)[2]).toEqual(['reveal', 58])
  })

  it('ignores picks and other reveals while the pair is highlighted', () => {
    const s = reveal(startGame([names]), () => 0)
    expect(pick(s, N(51))).toBe(s)
    expect(reveal(s)).toBe(s)
    expect(pick(clearReveal(s), N(51)).selected).toBe(N(51))
  })

  it('counts wrong guesses and reveals together as mistakes', () => {
    let s = tap(startGame([names]), N(49), M(50))
    s = clearReveal(reveal(s, () => 0))
    expect(mistakeCount(s)).toBe(2)
  })

  it('scores a revealed last pair as missed and still finishes the game', () => {
    let s = startGame([names])
    for (const p of names.pairs.slice(0, 9)) s = tap(s, N(p.id), M(p.id))
    s = reveal(s)
    expect(isGameOver(s)).toBe(true)
    expect(scoreSoFar(s)).toEqual({score: 9, total: 10})
    expect(squares(scoreGame(s.sets, s.guesses, 1).itemResults, s.sets)).toEqual(['🟩'.repeat(9) + '🟥'])
  })

  it('matches the server replay: reveal of a matched or unknown pair is rejected', () => {
    expect(scoreSet(names.pairs, [['reveal', 52]])).toEqual([null, null, null, false, null, null, null, null, null, null])
    expect(() => scoreSet(names.pairs, [[52, 52], ['reveal', 52]])).toThrow(/already matched/)
    expect(() => scoreSet(names.pairs, [['reveal', 52], [52, 52]])).toThrow(/already matched/)
    expect(() => scoreSet(names.pairs, [['reveal', 7]])).toThrow(/isn't in this set/)
  })

  it('a pair in an earlier wrong guess, then revealed, is still missed', () => {
    expect(scoreSet(names.pairs, [[52, 53], ['reveal', 52], [53, 53]]).slice(3, 5)).toEqual([false, false])
  })

  it('revealedIds lists the shown pairs across sets', () => {
    expect(revealedIds([[[1, 1], ['reveal', 2]], [['reveal', 16]]])).toEqual([2, 16])
  })
})

describe('deselect (Escape)', () => {
  it('clears the selection and logs nothing', () => {
    const s = deselect(pick(startGame([names]), N(49)))
    expect(s.selected).toBeNull()
    expect(allGuesses(s)).toEqual([])
  })
})

describe('lastEvent', () => {
  it('names each kind of change', () => {
    const s0 = startGame([names])
    const s1 = pick(s0, N(49))
    expect(lastEvent(s0, s1)).toEqual({kind: 'pick'})
    const s2 = pick(s1, M(49))
    expect(lastEvent(s1, s2)).toEqual({kind: 'match', pairId: 49, combo: 1})
    const s3 = pick(pick(s2, N(50)), M(50))
    expect(lastEvent(pick(s2, N(50)), s3)).toEqual({kind: 'match', pairId: 50, combo: 2})
    const s4 = pick(pick(s3, N(51)), M(52))
    expect(lastEvent(pick(s3, N(51)), s4)).toEqual({kind: 'wrong', pairIds: [51, 52]})
    const s5 = reveal(clearWrong(s4), () => 0)
    expect(lastEvent(clearWrong(s4), s5)).toEqual({kind: 'reveal', pairId: 51})
    expect(lastEvent(s5, clearReveal(s5))).toBeNull()
  })

  it('reports setCleared and finished', () => {
    const one = makeSet('names', [1])
    const two = makeSet('surahs', [2])
    const a = pick(startGame([one, two]), N(1))
    const b = pick(a, M(1))
    expect(lastEvent(a, b)).toEqual({kind: 'setCleared'})
    const c = pick(advanceSet(b), N(2))
    expect(lastEvent(c, pick(c, M(2)))).toEqual({kind: 'finished'})
  })
})
