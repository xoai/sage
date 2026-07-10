// Fixture for G3 — `left-pad` is declared in package.json, the other is not.
// Gate 4 must fail closed on the undeclared package, not merely warn.
import leftPad from 'left-pad';
import { render } from 'totally-not-a-real-package';

export const out = render(leftPad('x', 3));
