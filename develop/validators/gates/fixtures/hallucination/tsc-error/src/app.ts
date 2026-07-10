// Fixture for G5 — imports all resolve, but the toolchain rejects the types.
// Gate 4 must fail closed via tsc, not pass because no import is missing.
export const count: number = 'not a number';
