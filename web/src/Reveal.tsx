import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { still } from './motion.ts'

// GSAP and the React Bits pieces that use it come in their own chunk, fetched at once but off the
// first paint. With reduced motion it is never fetched, and if the fetch fails the page stays plain.
type Bits = typeof import('./bits/gsap.ts')
let loaded: Bits | null = null
const bits = still ? null : import('./bits/gsap.ts').then((m) => (loaded = m), () => null)

function useBits() {
  const [m, setM] = useState(loaded)
  useEffect(() => {
    if (!m) bits?.then((x) => x && setM(x))
  }, [m])
  return m
}

// the tagline's words come up out of a blur once the fonts are in
export function Tagline({ text }: { text: string }) {
  const m = useBits()
  // GSAP labels the split text with aria-label, which a <p> may not carry, so assistive tech reads a plain copy
  if (m)
    return (
      <>
        <p className="sr-only">{text}</p>
        <div aria-hidden="true">
          <m.SplitText tag="p" className="tagline" text={text} splitType="words" effect="blur" trigger="load" delay={45} duration={0.9} />
        </div>
      </>
    )
  // while the chunk loads the tagline waits unseen; CSS shows it anyway if the chunk is slow
  return <p className={still ? 'tagline' : 'tagline waiting'}>{text}</p>
}

// cards develop like a print in a tray: grey and soft, then sharp
export function Develop({ children, className, stagger }: { children: ReactNode; className?: string; stagger?: number }) {
  const m = useBits()
  if (!m) return <div className={className}>{children}</div>
  return (
    <m.FadeContent trigger="mount" effect="develop" duration={0.9} stagger={stagger} className={className}>
      {children}
    </m.FadeContent>
  )
}
