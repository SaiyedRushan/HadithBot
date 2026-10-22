import {createRoot} from 'react-dom/client'
import App from './App'
import {reducedMotion} from './ui'
import './index.css'

// Discord passes its own reduced motion setting in the launch URL. The CSS honours the
// system setting by itself; this class covers Discord's.
if (reducedMotion()) document.documentElement.classList.add('reduce-motion')

createRoot(document.getElementById('root')!).render(<App />)
