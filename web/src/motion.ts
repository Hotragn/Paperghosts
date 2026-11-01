import Lenis from 'lenis'
import 'lenis/dist/lenis.css'

// with reduced motion none of the motion starts: no smooth scroll, and text renders plain
export const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Lenis smooths the wheel only, and stops its glide when a link is followed; it leaves anchors, the skip link, focus and keyboard scrolling to the browser
export function startScroll() {
  if (!still) new Lenis({ autoRaf: true, stopInertiaOnNavigate: true })
}
