// Fixture for G1/G12 — the repro from 01-analysis §2.1.
// The relative import below resolves to nothing; Gate 4 must fail closed.
import { thing } from './does-not-exist';

export const value = thing;
