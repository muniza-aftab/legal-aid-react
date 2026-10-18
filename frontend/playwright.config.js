import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'

const root = path.resolve('..')
const windowsPython = path.join(root, 'backend/venv/Scripts/python.exe')
const python = process.env.PYTHON || (existsSync(windowsPython) ? windowsPython : 'python')
const remote = Boolean(process.env.E2E_BASE_URL)

export default defineConfig({
  testDir: './tests',
  timeout: 45000,
  expect: { timeout: 12000 },
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5178',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      args: ['--use-fake-device-for-media-stream'],
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}),
    },
  },
  webServer: remote ? undefined : [
    { command: `"${python}" -B tests/smoke_server.py`, cwd: path.join(root, 'backend'),
      url: 'http://127.0.0.1:8010/api/health', timeout: 30000, reuseExistingServer: false },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5178 --strictPort',
      url: 'http://127.0.0.1:5178', timeout: 30000, reuseExistingServer: false,
      env: { BACKEND_URL: 'http://127.0.0.1:8010' } },
  ],
})
