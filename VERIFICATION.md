# Feature repairs and verification

Date: 18 October 2026. The original, pre-repair findings are in [PROJECT_REVIEW.md](PROJECT_REVIEW.md). This report describes the repaired working tree; cloud production is a separate verification target.

## Implemented repairs

- Server-validated, expiring and revocable admin tokens protect case records, routing, analytics and registry mutations. Anonymous chat has an ownership token. Tokens are hashed in SQLite. Admin configuration fails closed when its password is absent.
- Case submission requires consent and saves the supplied CNIC and consent timestamp. New analytics entries omit raw queries/summaries by default. The UI now describes storage accurately.
- Assignments recalculate active workloads transactionally. Repeated assignment does not inflate counts; resolved cases remain resolved; deletion preserves referenced case history. Inactive NGOs are excluded from the public directory and new assignments.
- Case prompts fit the tested Groq account's token budget and use configurable available models. Citation checks reject unsupported law/section combinations in structured analysis. Risk matching avoids substring false alarms, and chat memory preserves user negation.
- Document review processes sequential text segments and reports coverage. TXT, DOCX tables, PDF and image extraction are supported. Uploads have format/size limits; OCR has a Groq vision fallback where native Tesseract is missing. Extraction and coverage warnings are visible.
- Vercel has SPA/API rewrites at either repository root setting. Local dev/preview share a configurable API proxy. Background model loading keeps public configuration available during warmup. Windows launchers use `call npm ci` and stop when setup fails.
- Frontend dependencies were updated, DOCX preview uses a smaller parser, and lint plus API/browser regression suites were added. A GitHub workflow runs the repeatable checks without provider keys.

## Verification evidence

| Check | Result | Scope |
| --- | --- | --- |
| Backend regression suite | 15 passed | Access/expiry/revocation, chat ownership, consent, CNIC, city filter, validation, privacy, workloads, registry history/availability, risk/negation, citation checks, document ending, uploads, DOCX tables, PDF and CORS |
| Playwright browser suite | 13 passed | Page navigation/refresh, backend outage, Urdu/RTL/theme persistence, mobile viewport, analysis/chat/audio/PDF, TXT/DOCX/PDF/image uploads, MediaRecorder/transcription, registry CRUD, application and admin workflows |
| Actual external AI/speech services | 10 passed | English/Urdu analysis, chat, document analysis, TTS and speech transcription using synthetic information and configured local provider keys |
| Actual vision OCR | Passed | Synthetic notice's deadline and reference number preserved |
| Regular localhost app | Passed | Backend ready, existing 13 NGOs/33 lawyers retained, private application reads rejected, 5 read-only browser checks passed |
| Actual HTTP integration | Passed | Synthetic analysis, owned chat and valid PDF through the regular Vite proxy and real provider |
| Frontend lint / production build | Passed | Vite production artifacts generated |
| Python dependency consistency | Passed | `pip check` |
| Production npm audit | 0 advisories | `npm audit --omit=dev` |
| Full npm audit | 7 development advisories remain | Legacy Tailwind/build dependency tree; major migration deferred |

Browser tests use real HTTP, extraction, authentication, routing and export with a disposable database. AI, speech and image OCR are stubbed in those repeatable tests. Separate opt-in live checks exercise actual providers; these are bounded smoke checks, not exhaustive assessments of legal correctness.

## Repeat checks

```powershell
cd backend
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -B -m unittest discover -s tests -p test_features.py -v
cd ../frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run build
npm.cmd audit --omit=dev
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

The browser suite starts its own isolated backend on 8010 and frontend on 5178. It writes only synthetic fixtures/results under ignored `.local/`, `test-results/` and `playwright-report/`. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` when using an existing compatible Chromium executable. Microphone capture uses a fake browser device.

Opt-in provider checks (use API quota): `cd backend; .\venv\Scripts\python.exe tests/live_smoke.py`. They use synthetic questions/documents, avoid the case database, and save results to ignored `.local/live-results.json`. For read-only hosted UI checks: set `E2E_BASE_URL` and run `npm.cmd run test:e2e -- --grep '@readonly'`. Do not run the complete mutation suite against a production database.

## Hosting status and limits

At inspection, the production Vercel homepage returned 200 but direct `/home` and `/document-analysis` requests returned 404. Render health eventually returned 200 after a cold start. Production still uses the original commit. The review branch `fix/local-vercel-feature-parity` was pushed to GitHub and Vercel reported a successful preview build. Preview deployment protection redirects automated browser visits to Vercel login, so hosted browser checks could not complete. HTTP 200 after that redirect is not evidence of an app route passing. Render's admin setting and database persistence must be confirmed before replacing the live backend. See [DEPLOYMENT.md](DEPLOYMENT.md).

Limits remain: document uploads are at most 10 MB, PDFs at most 50 pages (scanned PDFs at most 10), and AI document review at most 50,000 characters. Long review can return explicitly partial coverage. External provider quotas, network access and hosting cold starts affect availability. Chat history and rate-limit accounting are process-local; run one backend worker. Existing retrieval corpus coverage and legal currency still require specialist review; passing software tests does not certify legal advice or every possible input.
