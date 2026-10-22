/**
 * Arrow-key movement on the board, as pure functions.
 *
 * Ported from MugUp's pair-board-nav.ts. Matched cards are disabled, so the cursor steps
 * over them, the same as MugUp does.
 *
 * Two layouts:
 *   - The mixed grid (computers and tablets): left and right walk the cards in reading
 *     order, up and down go to the nearest open card in the row above or below.
 *   - The two phone columns: up and down stay in a column, left and right jump to the
 *     other column at the nearest open row (MugUp's moveBoardCursor, unchanged).
 */
import {parseCardKey, type Layout} from './game'

export type Move = 'up' | 'down' | 'left' | 'right'
export type BoardColumn = 0 | 1
export type BoardCursor = {col: BoardColumn; row: number}

/** The open row closest to `row`, or null when none is open. On a tie the row above wins. */
export function nearestOpenRow(open: readonly boolean[], row: number): number | null {
  const start = Math.min(Math.max(row, 0), open.length - 1)
  for (let distance = 0; distance < open.length; distance++) {
    if (open[start - distance]) return start - distance
    if (open[start + distance]) return start + distance
  }
  return null
}

/** Two columns: where the cursor goes on an arrow press. Nowhere to go leaves it in place. */
export function moveBoardCursor(open: readonly [readonly boolean[], readonly boolean[]], from: BoardCursor, move: Move): BoardCursor {
  if (move === 'left' || move === 'right') {
    const col: BoardColumn = move === 'left' ? 0 : 1
    if (col === from.col) return from
    const row = nearestOpenRow(open[col], from.row)
    return row == null ? from : {col, row}
  }
  const step = move === 'up' ? -1 : 1
  const column = open[from.col]
  for (let row = from.row + step; row >= 0 && row < column.length; row += step) {
    if (column[row]) return {col: from.col, row}
  }
  return from
}

/** Mixed grid with `cols` columns: the index the cursor moves to. Nowhere to go leaves it in place. */
export function moveInGrid(open: readonly boolean[], cols: number, from: number, move: Move): number {
  if (move === 'left' || move === 'right') {
    const step = move === 'left' ? -1 : 1
    for (let i = from + step; i >= 0 && i < open.length; i += step) {
      if (open[i]) return i
    }
    return from
  }
  const step = move === 'up' ? -1 : 1
  const fromCol = from % cols
  const rows = Math.ceil(open.length / cols)
  for (let row = Math.floor(from / cols) + step; row >= 0 && row < rows; row += step) {
    let best: number | null = null
    for (let col = 0; col < cols; col++) {
      const i = row * cols + col
      if (i >= open.length || !open[i]) continue
      if (best === null || Math.abs(col - fromCol) < Math.abs((best % cols) - fromCol)) best = i
    }
    if (best !== null) return best
  }
  return from
}

/** The open index closest to `from` in reading order, or null. On a tie the later card wins. */
export function nearestOpenIndex(open: readonly boolean[], from: number): number | null {
  const start = Math.min(Math.max(from, 0), open.length - 1)
  for (let distance = 0; distance < open.length; distance++) {
    if (open[start + distance]) return start + distance
    if (open[start - distance]) return start - distance
  }
  return null
}

export type BoardShape = {kind: 'grid'; cols: number} | {kind: 'columns'}

/** The card keys in the order the board shows them, for roving focus. */
export function boardKeys(layout: Layout, shape: BoardShape): string[] {
  if (shape.kind === 'grid') return layout.mixed
  return layout.names.flatMap((name, i) => [name, layout.meanings[i]])
}

/**
 * Moves the cursor (a card key) on either layout. With no cursor yet, or a cursor on a card
 * that has since been matched, an arrow press lands on the nearest open card first.
 * Returns null only when every card is matched.
 */
export function moveCursor(layout: Layout, matched: readonly number[], cursor: string | null, move: Move, shape: BoardShape): string | null {
  const isOpen = (key: string) => !matched.includes(parseCardKey(key).pairId)
  const settled = settleCursor(layout, matched, cursor, shape)
  if (settled === null) return null
  if (settled !== cursor) return settled

  if (shape.kind === 'grid') {
    const open = layout.mixed.map(isOpen)
    return layout.mixed[moveInGrid(open, shape.cols, layout.mixed.indexOf(settled), move)]
  }
  const columns = [layout.names, layout.meanings] as const
  const col: BoardColumn = parseCardKey(settled).side === 'name' ? 0 : 1
  const next = moveBoardCursor([layout.names.map(isOpen), layout.meanings.map(isOpen)], {col, row: columns[col].indexOf(settled)}, move)
  return columns[next.col][next.row]
}

/** The cursor if its card is still open, else the nearest open card. Null when all are matched. */
export function settleCursor(layout: Layout, matched: readonly number[], cursor: string | null, shape: BoardShape): string | null {
  const keys = boardKeys(layout, shape)
  const open = keys.map((k) => !matched.includes(parseCardKey(k).pairId))
  const at = cursor === null ? 0 : keys.indexOf(cursor)
  if (at >= 0 && open[at] && cursor !== null) return cursor
  const i = nearestOpenIndex(open, Math.max(at, 0))
  return i === null ? null : keys[i]
}
