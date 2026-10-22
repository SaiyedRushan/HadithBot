import {useEffect, useState, type ButtonHTMLAttributes, type ReactNode} from 'react'

type Variant = 'plain' | 'primary' | 'warn' | 'gold'

const VARIANTS: Record<Variant, string> = {
  plain: 'border-line text-[#dfe5ee] hover:bg-white/5',
  primary: 'border-ok-line bg-ok-line font-bold text-[#04140b] hover:brightness-110',
  warn: 'border-[#5a3324] text-[#f0b9a0] hover:bg-[#5a3324]/30',
  gold: 'border-[#c8883a] text-[#f3d3a3] hover:bg-[#c8883a]/15',
}

export function Button({variant = 'plain', className = '', ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {variant?: Variant}) {
  return (
    <button
      type="button"
      className={`cursor-pointer rounded-lg border px-3.5 py-2 text-sm font-medium leading-none transition disabled:cursor-default disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}

/** The page: dark background, content centred and capped at the mockup's width. */
export function Page({children}: {children: ReactNode}) {
  return (
    <main className="min-h-screen bg-game-bg font-sans text-[15px] leading-[1.45] text-[#e8e8e8]">
      <div className="mx-auto max-w-[980px] px-3 py-3.5 sm:px-[26px] sm:py-[22px]">{children}</div>
    </main>
  )
}

/** A centred screen with a heading, some text and maybe a button: loading, errors, outside Discord. */
export function Notice({title, children, action}: {title?: string; children: ReactNode; action?: ReactNode}) {
  return (
    <Page>
      <div className="mx-auto max-w-[600px] py-12 text-center">
        {title && <h1 className="mb-2 text-lg font-bold text-white sm:text-2xl">{title}</h1>}
        <div className="text-[#c9d1dc]">{children}</div>
        {action && <div className="mt-6">{action}</div>}
      </div>
    </Page>
  )
}

const PHONE_QUERY = '(max-width: 639.98px)'

/** Under 640px wide the game uses two columns instead of the mixed grid. */
export function useIsPhone(): boolean {
  const [isPhone, setIsPhone] = useState(() => window.matchMedia(PHONE_QUERY).matches)
  useEffect(() => {
    const mq = window.matchMedia(PHONE_QUERY)
    const onChange = () => setIsPhone(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return isPhone
}

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)
