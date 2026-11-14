import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export const NO_HTML = [
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: 'Render file strings as text, never as HTML.',
  },
  {
    selector: 'AssignmentExpression > MemberExpression[property.name=/^(innerHTML|outerHTML)$/]',
    message: 'Render file strings as text, never as HTML.',
  },
];

export default defineConfig([
  globalIgnores(['dist', 'test-results', 'playwright-report', 'src/api/schema.d.ts']),
  {
    files: ['**/*.{js,mjs}'],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    // Strings from files (names, labels, reasons) render as text, never as HTML (docs/API.md).
    files: ['src/**/*.{ts,tsx}'],
    rules: { 'no-restricted-syntax': ['error', ...NO_HTML] },
  },
]);
