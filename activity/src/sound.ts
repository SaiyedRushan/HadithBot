import {useState} from 'react'

/**
 * Short game sounds made with the Web Audio API, ported from MugUp's lib/sounds.ts (the
 * "classic" pack, a little quieter). No audio files, so there's nothing for Discord's
 * proxy to block. Every call fails silently: sound must never break the game.
 */

const STORAGE_KEY = 'hadithbot_sound'

function readSetting(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== 'off'
  } catch {
    // localStorage can throw inside an iframe. Default to on.
    return true
  }
}

let enabled = readSetting()
let audioContext: AudioContext | null = null

/**
 * Creates the AudioContext on a user gesture (a tap or key press). Browsers start it
 * suspended otherwise, and a sound scheduled then would play late or not at all.
 */
export function unlockAudio() {
  if (!enabled) return
  try {
    const Ctor = window.AudioContext ?? (window as {webkitAudioContext?: typeof AudioContext}).webkitAudioContext
    if (!Ctor) return
    audioContext ??= new Ctor()
    if (audioContext.state === 'suspended') void audioContext.resume()
  } catch {
    // no audio on this device
  }
}

type Tone = {freq: number; at?: number; duration?: number; type?: OscillatorType; gain?: number; glideTo?: number}

function playTones(tones: Tone[]) {
  const ctx = audioContext
  // A suspended context would play everything at once when it resumes, so skip this one.
  if (!ctx || ctx.state !== 'running') return
  const now = ctx.currentTime
  for (const {freq, at = 0, duration = 0.15, type = 'sine', gain = 0.08, glideTo} of tones) {
    const osc = ctx.createOscillator()
    const amp = ctx.createGain()
    osc.type = type
    osc.frequency.setValueAtTime(freq, now + at)
    if (glideTo) osc.frequency.exponentialRampToValueAtTime(glideTo, now + at + duration)
    amp.gain.setValueAtTime(0, now + at)
    amp.gain.linearRampToValueAtTime(gain, now + at + 0.01)
    amp.gain.exponentialRampToValueAtTime(0.0001, now + at + duration)
    osc.connect(amp).connect(ctx.destination)
    osc.start(now + at)
    osc.stop(now + at + duration + 0.05)
  }
}

export type Sound = 'pick' | 'match' | 'wrong' | 'reveal' | 'setCleared' | 'finished'

/** One semitone higher per match in a row, capped so a long streak doesn't squeak. */
const comboPitch = (root: number, combo: number) => root * Math.pow(2, Math.min(Math.max(combo - 1, 0), 8) / 12)

const TONES: Record<Sound, (combo: number) => Tone[]> = {
  pick: () => [{freq: 880, duration: 0.05, type: 'square', gain: 0.025}],
  match: (combo) => {
    const base = comboPitch(660, combo)
    return [
      {freq: base, duration: 0.1, gain: 0.07},
      {freq: base * 1.5, at: 0.08, duration: 0.18, gain: 0.08},
    ]
  },
  wrong: () => [
    {freq: 220, duration: 0.18, type: 'triangle', gain: 0.07, glideTo: 165},
    {freq: 110, duration: 0.18, gain: 0.05, glideTo: 82},
  ],
  // A soft falling pair of notes: help was given, not earned.
  reveal: () => [
    {freq: 587.33, duration: 0.16, type: 'triangle', gain: 0.06},
    {freq: 440, at: 0.12, duration: 0.24, type: 'triangle', gain: 0.06},
  ],
  setCleared: () => [
    {freq: 523.25, duration: 0.12, gain: 0.07},
    {freq: 659.25, at: 0.1, duration: 0.12, gain: 0.07},
    {freq: 783.99, at: 0.2, duration: 0.3, gain: 0.08},
  ],
  // MugUp's victory arpeggio: C5, E5, G5, C6 with a soft low root under the top note.
  finished: () => [
    {freq: 523.25, duration: 0.15, gain: 0.07},
    {freq: 659.25, at: 0.11, duration: 0.15, gain: 0.07},
    {freq: 783.99, at: 0.22, duration: 0.15, gain: 0.07},
    {freq: 1046.5, at: 0.33, duration: 0.4, gain: 0.09},
    {freq: 523.25, at: 0.33, duration: 0.4, type: 'triangle', gain: 0.04},
  ],
}

export function playSound(sound: Sound, combo = 0) {
  if (!enabled) return
  try {
    playTones(TONES[sound](combo))
  } catch {
    // never let audio break the game
  }
}

/** The "Sound: on" / "Sound: off" setting, remembered on this device. */
export function useSoundSetting(): [boolean, () => void] {
  const [on, setOn] = useState(enabled)
  const toggle = () => {
    enabled = !enabled
    setOn(enabled)
    try {
      window.localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off')
    } catch {
      // the setting just won't be remembered
    }
    if (enabled) unlockAudio()
  }
  return [on, toggle]
}
