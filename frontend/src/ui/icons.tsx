import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      width={16}
      height={16}
      {...props}
    >
      {children}
    </svg>
  )
}

export const FlagIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 17V3.5M4 4h10l-2 3.5L14 11H4" />
  </Icon>
)

export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m4.5 10.5 3.5 3.5 7.5-8" />
  </Icon>
)

export const XIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m5 5 10 10M15 5 5 15" />
  </Icon>
)

export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M16 10H4m5-5-5 5 5 5" />
  </Icon>
)

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 10h12m-5-5 5 5-5 5" />
  </Icon>
)

export const RefreshIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M16 10a6 6 0 1 1-1.8-4.3M16 3.5v3.2h-3.2" />
  </Icon>
)

export const SkipIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 10h10" />
  </Icon>
)

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" width={16} height={16} className={`animate-spin motion-reduce:animate-none ${className}`} aria-hidden="true">
      <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.5" />
      <path d="M17 10a7 7 0 0 0-7-7" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

/** Marks a label a reviewer corrected (pencil + screen-reader text). */
export function CorrectedMark() {
  return (
    <span className="inline-flex items-center text-ink-2">
      <Icon width={12} height={12}>
        <path d="m13.5 3.5 3 3L7 16H4v-3z" />
      </Icon>
      <span className="sr-only">(corrected)</span>
    </span>
  )
}
