// Hover explanations for the review screens (surveyor, checks, double-check), docs/ui-tooltips.md P1 and P2 rows.
// Two short sentences at most: what it is, what to do. Plain words; no code names. The rest live in tips.ts.

export const REVIEW_TIPS = {
  // Surveyor and conflicts (P1)
  conflictKicker: 'Two methods gave different numbers. A rule or a person picks the one to use.',
  choiceLocked: 'Someone signed this off, or it is saving. Undo the sign-off to change it.',
  // Takeoff (P1)
  takeoff: 'A takeoff is the list of everything counted or measured on this drawing.',
  colQuantity: 'What was counted or measured.',
  colValue: 'The number used.',
  colState: 'Whether it was checked, is in conflict, or is signed off.',
  // Quantity detail (P1)
  methods: 'Two independent ways of measuring the same thing.',
  keep: "Use this method's value.",
  settle: 'Use the value you typed.',
  settleLocked: 'Type a value first, or undo the sign-off to change it.',
  keepLocked: 'Undo the sign-off to change it.',
  signingAs: 'Your name goes on the sign-off.',
  signOff: 'You confirm this value is correct. Engineers see it as checked.',
  signOffLocked:
    'Type your name first. A value in conflict must be settled before it can be signed off.',
  undoSignOff: 'Takes the sign-off back so you can edit again.',
  // Takeoff and detail (P2)
  toReview: 'Values that need a person.',
  allOther: 'Values the methods already agree on.',
  resetAll: 'Undo every edit and sign-off on this drawing. Asks you to confirm.',
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
