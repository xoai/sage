import { greet } from './greeter';

it('greets', () => {
  expect(greet('world')).toBe('hi world');
});
