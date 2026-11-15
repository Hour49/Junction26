// Hover explanations for the plan viewer and the 3D view (docs/ui-tooltips.md, Plan and 3D rows).
// Two short sentences at most; plain words. shell/tips.ts holds the rest of the app's tips.

export const VIEWER_TIPS = {
  mark: 'One thing Vellum counted. The number matches the list of marks.',
  prevPage: 'Previous page of this sheet. Disabled on the first page.',
  nextPage: 'Next page of this sheet. Disabled on the last page.',
  pageLine: 'Marks are the doors, rooms and other things Vellum found on this page.',
  fixHint: 'Adds a mark Vellum missed. Only while you are fixing a count.',
} as const;
