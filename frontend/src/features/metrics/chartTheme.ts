/** Chart chrome from the design tokens (recessive: the data carries the colour). */
export const CHART = {
  grid: '#cfd2cc', // --color-line
  axis: '#6b706b', // --color-ink-3
  label: '#474b47', // --color-ink-2
  surface: '#ffffff', // --color-paper
  ink: '#000000', // --color-ink: single-series line
  hover: '#f1f2ef', // --color-sunken
  // Validated categorical pair (blue, orange) for the two-series chart
  series1: '#2a78d6',
  series2: '#eb6834',
}

export const axisTick = { fill: CHART.axis, fontSize: 12 }
export const categoryTick = { fill: CHART.label, fontSize: 12 }
