import type {Today} from './api'
import {gameStatus, otherGames, wording, type GameInfo, type GameKey} from './games'
import {Button} from './ui'

function GameCard({info, practice, current, children}: {info: GameInfo; practice: boolean; current?: boolean; children: React.ReactNode}) {
  return (
    <li
      className={`flex flex-col gap-3 rounded-xl border px-4 py-3.5 text-left sm:flex-row sm:items-center sm:justify-between ${
        current ? 'border-[#2f6aa8]/70 bg-[#0f1e30]/60' : 'border-white/[0.06] bg-game-panel'
      }`}>
      <div className="min-w-0">
        <h3 className="text-[15px] font-bold text-white">{info.title}</h3>
        <p className="text-sm text-[#98a2b3]">{info.detail}</p>
        {!practice && <p className={`mt-0.5 text-sm ${info.myResult ? 'font-semibold text-[#9be3bb]' : 'text-[#c9d1dc]'}`}>{gameStatus(info)}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </li>
  )
}

/** "Today's games" on the start screen: every game, the one shown above marked as such. */
export function TodaysGames({today, onOpen}: {today: Today; onOpen: (game: GameKey) => void}) {
  const games = today.games ?? []
  if (games.length < 2) return null
  const practice = today.mode === 'practice'
  return (
    <section className="mt-6" aria-labelledby="todays-games">
      <h2 id="todays-games" className="mb-2.5 text-[15px] font-bold text-white">
        {practice ? 'Games you can practise' : "Today's games"}
      </h2>
      <ul className="grid gap-2.5 sm:grid-cols-2">
        {games.map((info) => {
          const w = wording(info.key)
          const current = info.key === today.game
          return (
            <GameCard key={info.key} info={info} practice={practice} current={current}>
              {current ? (
                <span className="inline-block rounded-full border border-[#2f6aa8]/60 px-2.5 py-1 text-xs font-semibold text-[#8fb4dd]">Shown above</span>
              ) : (
                <Button variant={info.myResult ? 'plain' : 'primary'} onClick={() => onOpen(info.key)}>
                  {info.myResult && !practice ? w.seeResult : w.play}
                </Button>
              )}
            </GameCard>
          )
        })}
      </ul>
    </section>
  )
}

/** "Play another game today" on the result screen: the next step after a game. */
export function AnotherGame({today, onOpen}: {today: Today; onOpen: (game: GameKey) => void}) {
  const others = otherGames(today.games ?? [], today.game)
  if (others.length === 0) return null
  const practice = today.mode === 'practice'
  return (
    <section className="mt-4" aria-labelledby="another-game">
      <h2 id="another-game" className="mb-2.5 text-[15px] font-bold text-white">
        {practice ? 'Practise another game' : 'Play another game today'}
      </h2>
      <ul className="grid gap-2.5">
        {others.map((info) => (
          <GameCard key={info.key} info={info} practice={practice}>
            {info.myResult && !practice ? (
              <Button onClick={() => onOpen(info.key)}>See your result</Button>
            ) : (
              <Button variant="primary" className="px-4 py-2.5" onClick={() => onOpen(info.key)}>
                {wording(info.key).playWithCount}
              </Button>
            )}
          </GameCard>
        ))}
      </ul>
    </section>
  )
}
