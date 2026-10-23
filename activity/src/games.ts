/**
 * The daily match has more than one game (names of Allah, surahs of the Quran). This is
 * the wording that changes with the game, and the logic for listing the other games.
 * Pure, so it's tested. The names wording is exactly what the game said before surahs.
 */
import {formatDuration, type Result} from './game'

export type GameKey = 'names' | 'surahs'

/** One entry of `games` in GET /api/today. */
export type GameInfo = {key: GameKey; title: string; detail: string; myResult: Result | null}

export type Wording = {
  /** "Name match" in the page header. */
  header: string
  /** Screen-reader prefix for a left card: "Name", "Surah". */
  cardLabel: string
  /** Phone column header over the left cards. */
  column: string
  /** The small sample card on the start screen. */
  sample: string
  /** Heading on a phone, where the full title is too long. */
  phoneHeading: string
  rules: string
  /** "Play the surah match" */
  play: string
  /** "Play the surah match (10 surahs)" */
  playWithCount: string
  /** "See your surah match result" */
  seeResult: string
  boardHeading: string
  /** Added to "these 3" in the missed-pairs lists: "" for names (as before), " surahs" for surahs. */
  listNoun: string
  /** Used when a day's match arrives with no pairs. */
  empty: string
  learnHeading: string
  learnText: (missedAny: boolean) => string
  learnButton: string
}

/** Every game is 10 pairs. */
export const PAIRS_PER_GAME = 10

const WORDING: Record<GameKey, Wording> = {
  names: {
    header: 'Name match',
    cardLabel: 'Name',
    column: 'Names',
    sample: 'A name',
    phoneHeading: 'Match each name to its meaning',
    rules: 'Tap a name, then tap its meaning. You get a point for each name you match without a mistake. Showing a pair counts as a mistake.',
    play: 'Play the names match',
    playWithCount: `Play the names match (${PAIRS_PER_GAME} names)`,
    seeResult: 'See your names match result',
    boardHeading: 'Today in this server',
    listNoun: '',
    empty: "Today's match has no names in it. Close the game and press Play again later.",
    learnHeading: 'Want to learn all 99?',
    learnText: (missedAny) => `MugUp has every name as a matching game and flashcards${missedAny ? ', so you can practise the ones you missed.' : '.'}`,
    learnButton: 'Open the 99 names on MugUp',
  },
  surahs: {
    header: 'Surah match',
    cardLabel: 'Surah',
    column: 'Surahs',
    sample: 'A surah',
    phoneHeading: 'Match each surah to its meaning',
    rules: 'Tap a surah, then tap its meaning. You get a point for each surah you match without a mistake. Showing a pair counts as a mistake.',
    play: 'Play the surah match',
    playWithCount: `Play the surah match (${PAIRS_PER_GAME} surahs)`,
    seeResult: 'See your surah match result',
    boardHeading: 'Today in this server: surah match',
    listNoun: ' surahs',
    empty: "Today's surah match has no surahs in it. Close the game and press Play again later.",
    learnHeading: 'Want to learn all 114 surahs?',
    learnText: (missedAny) => `MugUp has every surah as a matching game${missedAny ? ', so you can practise the ones you missed.' : '.'}`,
    learnButton: 'Open the surahs on MugUp',
  },
}

export const isGameKey = (key: unknown): key is GameKey => key === 'names' || key === 'surahs'

/** The wording for a game. Anything unknown gets the names wording. */
export function wording(game: string | null | undefined): Wording {
  return isGameKey(game) ? WORDING[game] : WORDING.names
}

/** "Not played yet", or "You scored 9/10 in 52s" (the time is left out when there isn't one). */
export function gameStatus(info: GameInfo): string {
  const r = info.myResult
  if (!r) return 'Not played yet'
  const took = formatDuration(r.durationMs)
  return `You scored ${r.score}/${r.total}${took ? ` in ${took}` : ''}`
}

/** The games other than `current`, unplayed ones first, otherwise in the server's order. */
export function otherGames(games: readonly GameInfo[], current: string): GameInfo[] {
  const others = games.filter((g) => g.key !== current)
  return [...others.filter((g) => !g.myResult), ...others.filter((g) => g.myResult)]
}

/** The first game after `current` you haven't played today, or null. */
export function nextUnplayed(games: readonly GameInfo[], current: string): GameInfo | null {
  return otherGames(games, current).find((g) => !g.myResult) ?? null
}

/** A screen-reader label for a card: "Surah: 84. Al-Inshiqaq, الإنشقاق" or "Meaning: The Splitting Open". */
export function cardAriaLabel(game: string, side: 'name' | 'meaning', text: string, arabic: string | null | undefined, status: string): string {
  const prefix = side === 'name' ? wording(game).cardLabel : 'Meaning'
  return `${prefix}: ${text}${side === 'name' && arabic ? `, ${arabic}` : ''}${status}`
}
