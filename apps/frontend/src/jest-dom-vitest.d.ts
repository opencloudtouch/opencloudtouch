/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-empty-object-type, @typescript-eslint/no-unused-vars -- must mirror the vitest Assertion declaration */
import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers";

// @testing-library/jest-dom's own vitest augmentation declares Assertion with a
// single type parameter, which no longer matches vitest 5's Assertion<R, T>.
declare module "vitest" {
  interface Assertion<
    R extends void | Promise<void> = void,
    T = unknown,
  > extends TestingLibraryMatchers<any, R> {}
  interface AsymmetricMatchersContaining extends TestingLibraryMatchers<any, any> {}
}
