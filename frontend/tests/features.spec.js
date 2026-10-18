import { test, expect } from '@playwright/test'
import path from 'node:path'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('legal-aid-store')) localStorage.setItem('legal-aid-store', JSON.stringify({ state: { language: 'English', theme: 'dark' }, version: 0 }))
  })
})

test('all public pages open and refresh @readonly', async ({ page }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  for (const route of ['/', '/home', '/apply', '/document-analysis', '/ngos', '/lawyers', '/emergency', '/about']) {
    const response = await page.goto(route)
    expect(response.status(), route).toBe(200)
    await expect(page.locator('body')).not.toContainText('Loading Pakistan Legal Aid AI')
    await expect(page.locator('body')).not.toBeEmpty()
  }
  expect(errors).toEqual([])
})

test('emergency page renders while backend config is unavailable @readonly', async ({ page }) => {
  await page.route('**/api/config', route => route.abort())
  await page.goto('/emergency')
  await expect(page.locator('a[href="tel:15"]')).toBeVisible()
})

test('language picker, Urdu direction and theme work @readonly', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /اردو میں جاری رکھیں/ }).click()
  await expect(page).toHaveURL(/\/home$/)
  await expect(page.locator('html')).toHaveAttribute('lang', 'ur')
  await expect(page.locator('textarea').first()).toHaveAttribute('dir', 'rtl')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'ur')
  await page.getByTitle('Switch to light mode').click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
})

test('analysis, PDF download, chat and audio use the API', async ({ page }) => {
  await page.goto('/home')
  await page.locator('textarea').first().fill('My employer has not paid my salary for three months.')
  await page.getByRole('button', { name: 'Analyze Case', exact: true }).click()
  await expect(page.getByText('Browser test analysis: your wage-payment issue was reviewed.')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByTitle('Download Report').click()
  expect((await download).suggestedFilename()).toBe('legal_report.pdf')
  const listen = page.waitForResponse(response => response.url().endsWith('/api/tts'))
  await page.getByRole('button', { name: 'Listen', exact: true }).first().click()
  expect((await listen).status()).toBe(200)
  await page.getByRole('button', { name: 'Ask Legal AI', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.locator('textarea').fill('What payment records should I collect?')
  await dialog.locator('textarea').press('Enter')
  await expect(dialog.getByText('Browser test chat: collect your available payment records.')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
})

test('TXT document preview and analysis work', async ({ page }) => {
  await page.goto('/document-analysis')
  await page.locator('input[type="file"]').setInputFiles({
    name: 'notice.txt', mimeType: 'text/plain',
    buffer: Buffer.from('LEGAL NOTICE. This is a synthetic notice. Please respond within 14 days concerning unpaid salary.'),
  })
  await expect(page.getByText(/LEGAL NOTICE\. This is a synthetic notice/)).toBeVisible()
  await page.getByRole('button', { name: /Analyse with AI/ }).click()
  await expect(page.getByText('Browser test document analysis completed.')).toBeVisible()
})

for (const [file, expectedText] of [['contract.docx', 'SYNTHETIC CONTRACT PREVIEW'], ['contract.pdf', 'SYNTHETIC PDF CONTRACT PREVIEW'], ['notice.png', null]]) {
  test(`document upload and extraction: ${file}`, async ({ page }) => {
    await page.goto('/document-analysis')
    await page.locator('input[type="file"]').setInputFiles(path.resolve('../.local/browser-fixtures', file))
    if (expectedText) await expect(page.getByText(new RegExp(expectedText))).toBeVisible()
    else await expect(page.locator('img[alt="notice.png"]')).toBeVisible()
    await page.getByRole('button', { name: /Analyse with AI/ }).click()
    await expect(page.getByText('Browser test document analysis completed.')).toBeVisible()
  })
}

test('microphone recording and transcription populate the query', async ({ page, context }) => {
  await context.grantPermissions(['microphone'])
  await page.goto('/home')
  await page.getByRole('button', { name: 'Record', exact: true }).click()
  const stop = page.getByRole('button', { name: 'Stop', exact: true })
  await expect(stop).toBeVisible()
  await page.waitForTimeout(1200) // Capture at least one real MediaRecorder chunk.
  await stop.click()
  await expect(page.locator('textarea').first()).toHaveValue('My employer has not paid my salary for three months.')
})

test('registry create, update, availability and delete APIs work', async ({ request, page }) => {
  const login = await request.post('/api/admin/login', { data: { password: 'browser-test-password' } })
  const headers = { 'X-Admin-Token': (await login.json()).token }
  const ngo = await request.post('/api/ngos', { headers, data: { name: 'Registry Browser NGO', city: 'Karachi', categories: ['Family Law'] } })
  expect(ngo.ok()).toBe(true)
  const ngoId = (await ngo.json()).ngo_id
  const law = await request.post('/api/lawyers', { headers, data: { full_name: 'Registry Browser Lawyer', bar_license: 'BROWSER-REGISTRY-2', city: 'Karachi', expertise_main: 'Family Law', ngo_id: ngoId } })
  expect(law.ok()).toBe(true)
  const lawyerId = (await law.json()).lawyer_id
  await page.goto('/lawyers')
  await expect(page.getByText('Registry Browser Lawyer')).toBeVisible()
  expect((await request.patch(`/api/lawyers/${lawyerId}/availability`, { headers, data: { available: false } })).ok()).toBe(true)
  expect((await request.delete(`/api/ngos/${ngoId}`, { headers })).status()).toBe(409)
  expect((await request.delete(`/api/lawyers/${lawyerId}`, { headers })).ok()).toBe(true)
  expect((await request.put(`/api/ngos/${ngoId}`, { headers, data: { name: 'Updated Registry NGO', city: 'Karachi', categories: ['Family Law'] } })).ok()).toBe(true)
  expect((await request.delete(`/api/ngos/${ngoId}`, { headers })).ok()).toBe(true)
})

test('application, admin case routing and logout work', async ({ page }) => {
  await page.goto('/apply')
  await page.locator('[name="full_name"]').fill('Browser Synthetic Applicant')
  await page.locator('[name="phone"]').fill('03000000000')
  await page.locator('[name="city"]').selectOption('Karachi')
  await page.locator('[name="case_type"]').selectOption('Labour Law')
  await page.locator('[name="urgency"][value="Medium"]').check({ force: true })
  await page.locator('textarea[name="description"]').fill('This synthetic browser case concerns unpaid wages for three months.')
  await page.locator('[name="consent"]').check()
  await page.getByRole('button', { name: /Submit Application/ }).click()
  await expect(page.getByText(/APP-[A-F0-9]{16}/)).toBeVisible()
  await page.goto('/admin-portal')
  await page.getByPlaceholder('Admin password').fill('browser-test-password')
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible()
  for (const route of ['ngos', 'lawyers', 'analytics', 'routing']) {
    await page.goto(`/admin-portal/${route}`)
    await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible()
  }
  await expect(page.getByText('Browser Synthetic Applicant')).toBeVisible()
  await page.getByRole('button', { name: 'Logout', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin Access' })).toBeVisible()
})

test('directories filter without crashing @readonly', async ({ page }) => {
  await page.goto('/ngos')
  await expect(page.getByRole('textbox').first()).toBeVisible()
  await page.getByRole('textbox').first().fill('no-such-directory-record-12345')
  await expect(page.getByText('Browser Test Legal Support')).not.toBeVisible()
  await page.goto('/lawyers')
  await expect(page.getByRole('textbox').first()).toBeVisible()
  await page.getByRole('textbox').first().fill('no-such-directory-record-12345')
  await expect(page.getByText('Browser Test Advocate')).not.toBeVisible()
})

test('mobile pages stay within the viewport @readonly', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const path of ['/home', '/apply', '/document-analysis', '/ngos', '/lawyers']) {
    await page.goto(path)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(overflow, path).toBe(false)
  }
})
