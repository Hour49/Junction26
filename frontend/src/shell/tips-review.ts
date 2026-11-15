// Hover explanations for the review screens (conflicts, checks, double-check), docs/ui-tooltips.md P1 and P2 rows.
// Two short sentences at most: what it is, what to do. Plain words; no code names. The rest live in tips.ts.

export const REVIEW_TIPS = {
  // Conflicts (P1)
  conflictKicker: 'Two methods gave different numbers. A rule or a person picks the one to use.',
  choiceLocked: 'This value is saving or cannot be changed.',
  // Double-check (P1)
  doubleCheck: 'Two readers disagree about some marks, so a person should look.',
  fixing: 'You are editing the marks now. Press Done fixing when the count is right.',
  looksRight: 'Sign off the number as shown.',
  fixIt: 'Edit the marks first, then sign off.',
  // Double-check (P2)
  checkedByPerson: 'A person signed this answer off.',
  reject: 'Do not count this mark.',
  restore: 'Count this mark again.',
  // Checks (P2)
  preCheck: "A first pass against the country's rules. It is not a permit or a certificate.",
} as const;
