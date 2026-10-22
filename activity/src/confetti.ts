import confetti from 'canvas-confetti'
import {reducedMotion} from './ui'

const COLOURS = ['#2f9e63', '#5b9be0', '#e8b15a', '#c46a2b', '#ffffff']

/**
 * Confetti for a freshly finished run, bigger for a perfect score. Returns a cleanup.
 *
 * Draws on a canvas of our own with `useWorker: false`: the default worker is started from
 * a blob URL, which Discord's proxy CSP may block. Skipped entirely for reduced motion.
 */
export function celebrate(perfect: boolean): () => void {
  if (reducedMotion()) return () => {}
  const canvas = document.createElement('canvas')
  canvas.setAttribute('aria-hidden', 'true')
  canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:50'
  document.body.appendChild(canvas)

  let fire: confetti.CreateTypes | null = null
  const timers: ReturnType<typeof setTimeout>[] = []
  try {
    fire = confetti.create(canvas, {resize: true, useWorker: false})
    const shoot = fire
    if (perfect) {
      const side = (x: number, angle: number) => void shoot({particleCount: 70, angle, spread: 60, startVelocity: 55, origin: {x, y: 0.75}, colors: COLOURS})
      side(0, 60)
      side(1, 120)
      timers.push(setTimeout(() => void shoot({particleCount: 120, spread: 100, startVelocity: 45, origin: {y: 0.45}, colors: COLOURS}), 250))
      timers.push(
        setTimeout(() => {
          side(0, 60)
          side(1, 120)
        }, 600),
      )
    } else {
      void shoot({particleCount: 70, spread: 70, startVelocity: 38, origin: {y: 0.5}, colors: COLOURS, scalar: 0.9})
    }
  } catch {
    // no canvas support: no confetti
  }

  const end = () => {
    timers.forEach(clearTimeout)
    fire?.reset()
    canvas.remove()
  }
  timers.push(setTimeout(end, 6000))
  return end
}
