module.exports = {
  root: true,
  env: { browser: true, node: true, es2022: true },
  extends: ['eslint:recommended', 'plugin:react-hooks/recommended'],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
  ignorePatterns: ['dist', 'node_modules', '.npm-cache', 'playwright-report', 'test-results'],
  rules: {
    // The existing UI has unused decorative imports; retain useful runtime checks.
    'no-unused-vars': 'off',
    'no-empty': ['error', { allowEmptyCatch: true }],
    'react-hooks/exhaustive-deps': 'off',
  },
}
