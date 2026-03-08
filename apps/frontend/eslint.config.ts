import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import pluginReact from "eslint-plugin-react";
import pluginReactHooks from "eslint-plugin-react-hooks";

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/coverage/**",
      "**/tests/e2e/**",      // Keep e2e tests ignored (Cypress)
      "**/tests/real/**",     // Keep real hardware tests ignored
      "**/*.cy.*",            // Keep Cypress files ignored
      "**/*.min.js",
      "**/*.min.css",
      "**/*.css",  // CSS files handled by stylelint, not ESLint
      "**/*.json",
      "**/*.md"
    ]
  },
  {
    files: ["**/*.{js,mjs,cjs,ts,mts,cts,jsx,tsx}"],
    plugins: {
      react: pluginReact,
      "react-hooks": pluginReactHooks
    },
    settings: {
      react: {
        version: "detect"
      }
    },
    languageOptions: {
      globals: {
        ...globals.browser,
        // Node.js globals for config files (vite.config.js, cypress.config.js)
        ...globals.node
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      }
    },
    rules: {
      ...js.configs.recommended.rules,
      ...pluginReact.configs.recommended.rules,
      // React 18+ doesn't require React import in JSX files
      "react/react-in-jsx-scope": "off",
      // TypeScript migration complete - prop-types no longer needed
      "react/prop-types": "off",
      // Temporary: Disable display-name until eslint-plugin-react v8
      "react/display-name": "off",
      // React Hooks rules
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn"
    }
  },
  // Test files configuration
  {
    files: ["**/*.test.{ts,tsx}", "**/tests/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        // Vitest globals
        describe: "readonly",
        it: "readonly",
        expect: "readonly",
        vi: "readonly",
        beforeEach: "readonly",
        afterEach: "readonly",
        beforeAll: "readonly",
        afterAll: "readonly",
        test: "readonly"
      }
    }
  },
  ...tseslint.configs.recommended,
  // Override: allow intentionally-unused variables prefixed with _ (TypeScript convention)
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          varsIgnorePattern: "^_",
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_"
        }
      ]
    }
  }
];
