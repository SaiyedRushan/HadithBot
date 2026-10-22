import {useEffect, useState, type ButtonHTMLAttributes, type ReactNode} from 'react'

type Variant = 'plain' | 'primary' | 'warn' | 'gold' | 'reveal'

const VARIANTS: Record<Variant, string> = {
  plain: 'border-line bg-white/[0.02] text-[#dfe5ee] hover:border-[#3b4a5e] hover:bg-white/[0.06]',
  primary: 'border-ok-line bg-ok-line font-bold text-[#04140b] shadow-[0_6px_20px_-8px_rgba(47,158,99,.7)] hover:brightness-110',
  warn: 'border-[#5a3324] text-[#f0b9a0] hover:border-[#7a4532] hover:bg-[#5a3324]/30',
  gold: 'border-[#c8883a] text-[#f3d3a3] hover:bg-[#c8883a]/15',
  reveal: 'border-[#6b5326] text-[#f1d39b] hover:border-[#8a6a2f] hover:bg-[#6b5326]/25',
}

export function Button({variant = 'plain', className = '', ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {variant?: Variant}) {
  return (
    <button
      type="button"
      className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium leading-tight transition duration-150 active:scale-[0.97] disabled:cursor-default disabled:opacity-45 disabled:active:scale-100 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}

/** A key name shown on a control, only on devices with a keyboard and mouse. */
export function Kbd({children}: {children: ReactNode}) {
  return (
    <kbd className="rounded border border-white/15 bg-black/25 px-1.5 py-px font-sans text-[11px] font-semibold leading-4 text-current opacity-80">{children}</kbd>
  )
}

/** HadithBot's mark and name, with whatever belongs on the right (the sound setting). */
export function Header({place, right}: {place?: string | null; right?: ReactNode}) {
  return (
    <header className="mb-5 flex items-center justify-between gap-3 border-b border-white/[0.06] pb-3 sm:mb-6">
      <div className="flex min-w-0 items-center gap-2.5">
        <img src="/hadithbot.png" alt="" width={32} height={32} className="h-8 w-8 shrink-0 rounded-full ring-1 ring-[#c8883a]/60" />
        <div className="min-w-0 leading-tight">
          <div className="text-sm font-semibold text-white">HadithBot</div>
          <div className="truncate text-xs text-[#7f8a9a]">Name match{place ? ` · ${place}` : ''}</div>
        </div>
      </div>
      {right}
    </header>
  )
}

/** The page: dark background, content centred and capped at the mockup's width. */
export function Page({children, place, headerRight}: {children: ReactNode; place?: string | null; headerRight?: ReactNode}) {
  return (
    <main className="min-h-screen bg-game-bg bg-[radial-gradient(ellipse_at_top,rgba(47,106,168,0.12),transparent_60%)] font-sans text-[15px] leading-[1.5] text-[#e8e8e8] antialiased">
      <div className="mx-auto max-w-[980px] px-3 py-3.5 sm:px-[26px] sm:py-[22px]">
        <Header place={place} right={headerRight} />
        {children}
      </div>
    </main>
  )
}

export function Panel({children, className = ''}: {children: ReactNode; className?: string}) {
  return <div className={`rounded-xl border border-white/[0.06] bg-game-panel ${className}`}>{children}</div>
}

export function Spinner() {
  return <span aria-hidden className="mx-auto mb-4 block h-7 w-7 animate-spin rounded-full border-2 border-[#2f6aa8]/30 border-t-[#5b9be0]" />
}

/** A centred screen with a heading, some text and maybe a button: loading, errors, outside Discord. */
export function Notice({title, children, action, busy}: {title?: string; children: ReactNode; action?: ReactNode; busy?: boolean}) {
  return (
    <Page>
      <Panel className="anim-rise mx-auto mt-6 max-w-[560px] px-5 py-8 text-center sm:mt-12 sm:px-8 sm:py-10">
        {busy && <Spinner />}
        {title && <h1 className="mb-2 text-lg font-bold text-white sm:text-xl">{title}</h1>}
        <div role={busy ? 'status' : undefined} className="text-[#c9d1dc]">
          {children}
        </div>
        {action && <div className="mt-6">{action}</div>}
      </Panel>
    </Page>
  )
}

function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const onChange = () => setMatches(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [query])
  return matches
}

/** Under 640px wide the game uses two columns instead of the mixed grid. */
export const useIsPhone = () => useMedia('(max-width: 639.98px)')

/** A mouse or trackpad, so there's very likely a keyboard: show the key hints. */
export const useFinePointer = () => useMedia('(hover: hover) and (pointer: fine)')

/** Columns in the mixed grid: 5 from Tailwind's md breakpoint (768px), 3 below it. */
export const useGridColumns = () => (useMedia('(min-width: 768px)') ? 5 : 3)

/** The player's system setting, or Discord's own reduced motion setting (passed in the URL). */
export function reducedMotion(): boolean {
  try {
    if (new URLSearchParams(window.location.search).get('reduced_motion') === 'true') return true
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

/** The "Powered by MugUp" section on the start and result screens. */
export function PoweredByMugup({onOpen}: {onOpen: () => void}) {
  return (
    <section className="mt-8 border-t border-white/[0.06] pt-6 text-left" aria-labelledby="powered-by">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <img src="/mugup-logo.png" alt="MugUp logo" width={48} height={48} className="h-12 w-12 shrink-0 rounded-xl bg-white/95 p-1" />
        <div className="min-w-0 flex-1">
          <h2 id="powered-by" className="mb-1 text-[15px] font-bold text-white">
            Powered by MugUp
          </h2>
          <p className="max-w-[640px] text-sm text-[#aeb7c3]">
            This game comes from MugUp. MugUp's own Discord app can run a daily challenge in any channel from any public deck: the same 12 questions for
            everyone, a leaderboard, and the fastest run wins a tie. Link a free MugUp account and your runs go on a spaced review schedule, so questions you get
            wrong come back sooner and ones you know come back later.
          </p>
          <Button className="mt-3" onClick={onOpen}>
            Open MugUp's Discord app page ↗
          </Button>
        </div>
      </div>
    </section>
  )
}

export const MUGUP_DISCORD_URL = 'https://mugup.app/discord'
