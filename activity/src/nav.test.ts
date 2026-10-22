import {describe, expect, it} from 'vitest'
import {cardKey, type Layout} from './game'
import {moveBoardCursor, moveCursor, moveInGrid, nearestOpenIndex, nearestOpenRow, settleCursor} from './nav'

const N = (id: number) => cardKey('name', id)
const M = (id: number) => cardKey('meaning', id)

describe('nearestOpenRow (MugUp)', () => {
  it('keeps an open row, prefers the row above on a tie, clamps, and gives null when all are matched', () => {
    expect(nearestOpenRow([true, true, true], 1)).toBe(1)
    expect(nearestOpenRow([true, false, true], 1)).toBe(0)
    expect(nearestOpenRow([false, false, false, true], 0)).toBe(3)
    expect(nearestOpenRow([true, true], 4)).toBe(1)
    expect(nearestOpenRow([false, false], 0)).toBeNull()
  })
})

describe('moveBoardCursor (two phone columns, MugUp)', () => {
  const allOpen: [boolean[], boolean[]] = [
    [true, true, true, true],
    [true, true, true, true],
  ]

  it('moves within a column and stops at the ends', () => {
    expect(moveBoardCursor(allOpen, {col: 0, row: 1}, 'down')).toEqual({col: 0, row: 2})
    expect(moveBoardCursor(allOpen, {col: 0, row: 0}, 'up')).toEqual({col: 0, row: 0})
    expect(moveBoardCursor(allOpen, {col: 0, row: 3}, 'down')).toEqual({col: 0, row: 3})
  })

  it('steps over matched cards', () => {
    const open: [boolean[], boolean[]] = [
      [true, false, false, true],
      [true, true, true, true],
    ]
    expect(moveBoardCursor(open, {col: 0, row: 0}, 'down')).toEqual({col: 0, row: 3})
  })

  it('crosses to the nearest open row in the other column, or stays when it is all matched', () => {
    const open: [boolean[], boolean[]] = [
      [true, true, true, true],
      [true, true, false, true],
    ]
    expect(moveBoardCursor(open, {col: 0, row: 2}, 'right')).toEqual({col: 1, row: 1})
    expect(moveBoardCursor(open, {col: 1, row: 2}, 'right')).toEqual({col: 1, row: 2})
    expect(moveBoardCursor([[true], [false]], {col: 0, row: 0}, 'right')).toEqual({col: 0, row: 0})
  })
})

describe('moveInGrid (mixed grid)', () => {
  // 5 columns, 4 rows
  const all = Array(20).fill(true)

  it('moves by one column left and right, and by one row up and down', () => {
    expect(moveInGrid(all, 5, 7, 'right')).toBe(8)
    expect(moveInGrid(all, 5, 7, 'left')).toBe(6)
    expect(moveInGrid(all, 5, 7, 'down')).toBe(12)
    expect(moveInGrid(all, 5, 7, 'up')).toBe(2)
  })

  it('wraps left and right across rows in reading order, but not past the ends', () => {
    expect(moveInGrid(all, 5, 4, 'right')).toBe(5)
    expect(moveInGrid(all, 5, 5, 'left')).toBe(4)
    expect(moveInGrid(all, 5, 19, 'right')).toBe(19)
    expect(moveInGrid(all, 5, 0, 'left')).toBe(0)
    expect(moveInGrid(all, 5, 2, 'up')).toBe(2)
    expect(moveInGrid(all, 5, 17, 'down')).toBe(17)
  })

  it('steps over matched cards', () => {
    const open = [...all]
    open[8] = false
    open[9] = false
    expect(moveInGrid(open, 5, 7, 'right')).toBe(10)
    open[12] = false
    expect(moveInGrid(open, 5, 7, 'down')).toBe(11)
  })

  it('on up and down, goes to the closest open column in the next row that has one', () => {
    const open = [...all]
    for (let i = 10; i < 15; i++) open[i] = false
    open[17] = false
    expect(moveInGrid(open, 5, 7, 'down')).toBe(16)
  })

  it('handles a short last row', () => {
    const open = Array(7).fill(true)
    expect(moveInGrid(open, 3, 2, 'down')).toBe(5)
    expect(moveInGrid(open, 3, 5, 'down')).toBe(6)
  })
})

describe('nearestOpenIndex', () => {
  it('prefers the later card on a tie and gives null when all are matched', () => {
    expect(nearestOpenIndex([true, false, true], 1)).toBe(2)
    expect(nearestOpenIndex([true, false, false], 2)).toBe(0)
    expect(nearestOpenIndex([false, false], 0)).toBeNull()
  })
})

describe('moveCursor', () => {
  const layout: Layout = {
    mixed: [N(1), M(2), N(2), M(1), N(3), M(3)],
    names: [N(2), N(1), N(3)],
    meanings: [M(3), M(1), M(2)],
  }

  it('lands on the first open card on the first press', () => {
    expect(moveCursor(layout, [], null, 'down', {kind: 'grid', cols: 3})).toBe(N(1))
    expect(moveCursor(layout, [], null, 'down', {kind: 'columns'})).toBe(N(2))
  })

  it('moves on the grid and in the columns', () => {
    expect(moveCursor(layout, [], N(1), 'down', {kind: 'grid', cols: 3})).toBe(M(1))
    expect(moveCursor(layout, [], N(1), 'right', {kind: 'columns'})).toBe(M(1))
    expect(moveCursor(layout, [], N(1), 'down', {kind: 'columns'})).toBe(N(3))
  })

  it('moves off a card that has just been matched', () => {
    expect(moveCursor(layout, [1], N(1), 'right', {kind: 'grid', cols: 3})).toBe(M(2))
    expect(settleCursor(layout, [1, 2, 3], N(1), {kind: 'grid', cols: 3})).toBeNull()
  })
})
