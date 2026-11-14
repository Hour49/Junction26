// The surveyor's button looks on shadcn's Button (surveyor.md "Vellum look"): soft pills, semibold.
// shrink + max-w-full: a long label wraps inside the card at 390 px instead of running past it. Disabled: grey, as
// before, not shadcn's half-faded colour.
const PILL =
  'v-press h-auto max-w-full shrink rounded-full px-3.5 py-1 text-base font-semibold whitespace-normal disabled:bg-secondary disabled:text-muted-foreground disabled:opacity-100';
/** A soft pill in a tool row (40 px), the selected quantity's (44 px), the panel head's (32 px, 40 on a phone). */
export const TOOL = `${PILL} min-h-10`;
export const DETAIL = `${PILL} min-h-11`;
export const HEAD = `${PILL} min-h-8 max-[760px]:min-h-10`;
/** The destructive one: danger text on the soft fill. */
export const DANGER = 'text-danger hover:text-danger';
/** A takeoff row's label: a quiet button filling its cell. */
export const ROW =
  'v-press h-auto min-h-8 w-full justify-start rounded-full px-2 py-0.5 text-left font-normal whitespace-normal max-[760px]:min-h-10';
/** The surveyor's text fields: 40 px, 16 px text (no iOS zoom on focus). */
export const FIELD = 'h-10 rounded-xl bg-card px-3 text-base md:text-base';
