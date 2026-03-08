#!/usr/bin/env node
/**
 * Pre-commit hook: block new .js test files (TypeScript migration complete)
 * Replaces the bash-based hook for cross-platform compatibility on Windows.
 */
import { execSync } from 'child_process';

const staged = execSync('git diff --cached --name-only --diff-filter=A')
  .toString()
  .split('\n')
  .filter(f => f.match(/\.(test|spec)\.js$/));

if (staged.length > 0) {
  console.error('ERROR - New .js test files not allowed. Use .ts/.tsx instead:');
  staged.forEach(f => console.error('  ' + f));
  process.exit(1);
}
