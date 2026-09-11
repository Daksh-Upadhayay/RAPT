/** Class recipes shared by components (and usable on elements that aren't components). */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-label font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-45'

const VARIANTS: Record<ButtonVariant, string> = {
  // Postal yellow with black print: the one action that moves work forward
  primary: 'bg-accent text-ink hover:bg-accent-deep disabled:hover:bg-accent',
  secondary: 'border border-ink bg-paper text-ink hover:bg-sunken disabled:hover:bg-paper',
  ghost: 'text-ink-2 hover:bg-ink/5 hover:text-ink',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-small',
  md: 'h-10 px-4 text-small',
}

export function buttonClasses(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', extra = ''): string {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${extra}`
}

const CONTROL =
  'block w-full rounded-label border bg-paper px-3 text-body text-ink placeholder:text-ink-3 focus:border-ink focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink disabled:bg-sunken disabled:text-ink-3'

export function controlClasses(invalid = false, extra = ''): string {
  return `${CONTROL} ${invalid ? 'border-danger' : 'border-ink/35 hover:border-ink/60'} ${extra}`
}

