/**
 * fileParser.js — client-side text extraction for .txt / .docx / .pdf
 *
 * Libraries:
 *   mammoth    — extracts raw UTF-8 text from .docx (Word XML, Urdu-safe)
 *   pdfjs-dist — renders PDF pages and returns Unicode text items
 *
 * Both preserve full Unicode (Urdu, Arabic, etc.) without any extra steps
 * because DOCX stores text as XML and PDF text items are already decoded
 * Unicode strings by the time they reach the JS layer.
 */

import { unzipSync, strFromU8 } from 'fflate'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

// Point pdfjs to the locally-bundled worker (Vite resolves the ?url import)
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

// CMap data is needed to correctly decode Arabic / Urdu / CJK glyphs in PDFs.
// We load them from the CDN that matches the installed pdfjs version.
const CMAP_URL = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/cmaps/`
const FONT_URL  = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/standard_fonts/`

// ─── .txt ────────────────────────────────────────────────────────────────────
async function extractTxt(file) {
  return await file.text()          // Browser File.text() is always UTF-8
}

// ─── .docx ───────────────────────────────────────────────────────────────────
async function extractDocx(file) {
  const arrayBuffer = await file.arrayBuffer()
  const files = unzipSync(new Uint8Array(arrayBuffer), {
    filter: entry => entry.name === 'word/document.xml' && entry.originalSize <= 10 * 1024 * 1024,
  })
  const xmlBytes = files['word/document.xml']
  if (!xmlBytes || xmlBytes.length > 10 * 1024 * 1024) throw new Error('This Word document is damaged or too large.')
  const xml = new DOMParser().parseFromString(strFromU8(xmlBytes), 'application/xml')
  if (xml.querySelector('parsererror')) throw new Error('This Word document contains invalid XML.')
  const namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  return [...xml.getElementsByTagNameNS(namespace, 'p')]
    .map(paragraph => [...paragraph.getElementsByTagNameNS(namespace, 't')].map(node => node.textContent).join(''))
    .join('\n')
}

// ─── .pdf ────────────────────────────────────────────────────────────────────
async function extractPdf(file) {
  const arrayBuffer = await file.arrayBuffer()

  const pdf = await pdfjsLib.getDocument({
    data: new Uint8Array(arrayBuffer),
    cMapUrl: CMAP_URL,
    cMapPacked: true,               // Required for Arabic/Urdu glyph mapping
    standardFontDataUrl: FONT_URL,
  }).promise

  const pages = []

  for (let i = 1; i <= pdf.numPages; i++) {
    const page    = await pdf.getPage(i)
    const content = await page.getTextContent()

    // hasEOL marks the end of a visual line — preserves paragraph breaks
    const pageText = content.items
      .map(item => item.str + (item.hasEOL ? '\n' : ' '))
      .join('')
      .replace(/ {2,}/g, ' ')      // Collapse duplicate spaces
      .trim()

    if (pageText) pages.push(pageText)
  }

  return pages.join('\n\n')
}

// ─── Public API ───────────────────────────────────────────────────────────────
/**
 * Extract readable text from a File object.
 * Supports: .txt  .docx  .pdf
 * Returns a UTF-8 string (Urdu, Arabic, etc. preserved as-is).
 * Throws a user-readable Error on unsupported types or parse failures.
 */
export async function extractTextFromFile(file) {
  if (file.size > 10 * 1024 * 1024) throw new Error('Files must be 10 MB or smaller.')
  const name = file.name.toLowerCase()

  if (name.endsWith('.txt'))  return extractTxt(file)
  if (name.endsWith('.docx')) return extractDocx(file)
  if (name.endsWith('.pdf'))  return extractPdf(file)

  throw new Error('Unsupported file type. Please upload a .txt, .docx, or .pdf file.')
}
