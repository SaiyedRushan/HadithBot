import {describe, expect, it} from 'vitest'
import {cardAriaLabel, gameStatus, nextUnplayed, otherGames, wording, type GameInfo} from './games'

const names = (myResult: GameInfo['myResult'] = null): GameInfo => ({key: 'names', title: 'Names of Allah', detail: "10 names of Allah, including today's", myResult})
const surahs = (myResult: GameInfo['myResult'] = null): GameInfo => ({
  key: 'surahs',
  title: 'Surahs of the Quran',
  detail: '10 surahs of the Quran, a different 10 each day',
  myResult,
})
const played = (score: number, durationMs: number | null) => ({score, total: 10, itemResults: [], durationMs})

describe('wording', () => {
  it('keeps the names wording the game used before surahs', () => {
    const w = wording('names')
    expect(w.rules).toBe('Tap a name, then tap its meaning. You get a point for each name you match without a mistake. Showing a pair counts as a mistake.')
    expect(w.boardHeading).toBe('Today in this server')
    expect(w.column).toBe('Names')
    expect(w.learnHeading).toBe('Want to learn all 99?')
    expect(w.learnButton).toBe('Open the 99 names on MugUp')
    expect(w.learnText(true)).toBe('MugUp has every name as a matching game and flashcards, so you can practise the ones you missed.')
    expect(w.learnText(false)).toBe('MugUp has every name as a matching game and flashcards.')
    expect(w.listNoun).toBe('')
  })

  it('has surah wording for every place that names a game', () => {
    const w = wording('surahs')
    expect(w.rules).toBe('Tap a surah, then tap its meaning. You get a point for each surah you match without a mistake. Showing a pair counts as a mistake.')
    expect(w.column).toBe('Surahs')
    expect(w.boardHeading).toBe('Today in this server: surah match')
    expect(w.play).toBe('Play the surah match')
    expect(w.playWithCount()).toBe('Play the surah match (10 surahs)')
    expect(wording('words').playWithCount(11)).toBe('Play the Quranic word match (11 words)')
    expect(w.seeResult).toBe('See your surah match result')
    expect(w.learnHeading).toBe('Want to learn all 114 surahs?')
    expect(w.learnText(true)).toBe('MugUp has every surah as a matching game, so you can practise the ones you missed.')
    expect(w.learnButton).toBe('Open the surahs on MugUp')
  })

  it('falls back to names for an unknown or missing game', () => {
    expect(wording('quiz')).toBe(wording('names'))
    expect(wording(undefined)).toBe(wording('names'))
  })

  it('never uses an em or en dash', () => {
    for (const key of ['names', 'surahs', 'words']) {
      const w = wording(key)
      const text = [...Object.values(w).filter((v) => typeof v === 'string'), w.learnText(true), w.learnText(false)].join(' ')
      expect(text).not.toMatch(/[\u2013\u2014]/)
    }
  })
})

describe('gameStatus', () => {
  it('says whether you have played and what you scored', () => {
    expect(gameStatus(surahs())).toBe('Not played yet')
    expect(gameStatus(surahs(played(9, 52000)))).toBe('You scored 9/10 in 52s')
    expect(gameStatus(names(played(10, 65000)))).toBe('You scored 10/10 in 1m 05s')
    expect(gameStatus(names(played(4, null)))).toBe('You scored 4/10')
  })
})

describe('otherGames and nextUnplayed', () => {
  it('lists the games other than the current one', () => {
    expect(otherGames([names(), surahs()], 'names').map((g) => g.key)).toEqual(['surahs'])
    expect(otherGames([names(), surahs()], 'surahs').map((g) => g.key)).toEqual(['names'])
  })

  it('puts unplayed games first', () => {
    const third = {...surahs(), key: 'names' as const, title: 'Third'}
    const list = otherGames([names(), surahs(played(5, 1000)), {...third, myResult: null}], 'x')
    expect(list.map((g) => g.title)).toEqual(['Names of Allah', 'Third', 'Surahs of the Quran'])
  })

  it('finds the next game you have not played, or null', () => {
    expect(nextUnplayed([names(played(9, 1000)), surahs()], 'names')?.key).toBe('surahs')
    expect(nextUnplayed([names(), surahs(played(9, 1000))], 'surahs')?.key).toBe('names')
    expect(nextUnplayed([names(), surahs(played(9, 1000))], 'names')).toBeNull()
    expect(nextUnplayed([names()], 'names')).toBeNull()
  })
})

describe('cardAriaLabel', () => {
  it('starts with what kind of card it is', () => {
    expect(cardAriaLabel('surahs', 'name', '84. Al-Inshiqaq', 'الإنشقاق', '')).toBe('Surah: 84. Al-Inshiqaq, الإنشقاق')
    expect(cardAriaLabel('surahs', 'meaning', 'The Splitting Open', 'الإنشقاق', ', matched')).toBe('Meaning: The Splitting Open, matched')
    expect(cardAriaLabel('names', 'name', "49. Al-Baa'ith", null, '')).toBe("Name: 49. Al-Baa'ith")
  })
})
