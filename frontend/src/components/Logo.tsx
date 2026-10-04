import { motion } from 'framer-motion'

/** Wordmark: green check + "Definitely Human™", matching the brand logo. */
export function Logo({ height = 34, animate = true }: { height?: number; animate?: boolean }) {
  return (
    <svg className="logo-word" height={height} viewBox="0 0 590 80" role="img" aria-label="Definitely Human™">
      <motion.path
        d="M10 44 L30 64 L66 14"
        fill="none"
        stroke="#1a7f52"
        strokeWidth="13"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={animate ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
      />
      <text x="80" y="62" fontFamily="Outfit" fontWeight="750" fontSize="58" fill="#111418" letterSpacing="-1">
        Definitely Human<tspan dx="3" dy="-30" fontSize="16" fontWeight="600">™</tspan>
      </text>
    </svg>
  )
}

/** Animated check that draws itself — used on loading screens. */
export function DrawCheck({ size = 72, loop = false }: { size?: number; loop?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 80 80">
      <motion.circle cx="40" cy="40" r="36" fill="#e3f3ea"
        initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.4 }} />
      <motion.path
        d="M22 42 L35 55 L59 27"
        fill="none" stroke="#1a7f52" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={loop
          ? { duration: 1.1, ease: 'easeInOut', repeat: Infinity, repeatType: 'reverse', repeatDelay: 0.3 }
          : { duration: 0.6, delay: 0.2 }}
      />
    </svg>
  )
}
