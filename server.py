#!/usr/bin/env python3
"""
Servidor Flask para la interfaz de análisis de bebidas.
Sirve el frontend y gestiona las llamadas a la API de Gemma.
"""

import base64
import json
import os
from io import BytesIO
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template_string, request, send_from_directory
from PIL import Image

app = Flask(__name__)

DATASET_DIR = Path("./dataset")
MAX_SIZE = (512, 512)
JPEG_QUALITY = 70

DEFAULT_PROMPT = (
    "Actua como un experto en branding. Identifica la bebida de la imagen. "
    "Ten en cuenta que la etiqueta puede ser muy grande y no leerse completa. "
    "Si no encuentras la etiqueta, y por lo tanto no estas 100% seguro de la marca, responde con ERROR. "
    "No es admisible que el nombre de la marca detectada sea erroneo, es preferible responder con un error a la minima duda. "
    "Quiero saber el tipo de envase (botella o lata) y su estado. "
    "Quiero una respuesta en formato json siguiendo el siguiente esquema:\n"
    '{\n  "objects": [\n    {\n      "type": "BOTTLE | CAN | ERROR",\n'
    '      "name": "BRAND NAME | ERROR IF NONE FOUND",\n'
    '      "status": "OK | NO OK",\n'
    '      "description": "DESCRIPCION CORTA"\n    }\n  ]\n}\n'
    "Si no hay ninguna bebida, responde ERROR.\n"
    "Responde SOLO con el JSON, sin texto adicional, sin bloques de código markdown."
)

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Beverage Analyzer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0a;
    --surface: #111111;
    --surface2: #1a1a1a;
    --border: #2a2a2a;
    --accent: #c8f542;
    --accent2: #f5d442;
    --text: #f0f0f0;
    --muted: #666;
    --danger: #ff4d4d;
    --ok: #4dff91;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr;
    overflow-x: hidden;
  }

  /* ── Header ── */
  header {
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2.5rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    background: var(--surface);
  }
  .logo-mark {
    width: 36px; height: 36px;
    background: var(--accent);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    color: #000;
    font-size: 1rem;
    flex-shrink: 0;
  }
  .header-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }
  .header-sub {
    font-size: 0.7rem;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .api-config {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .api-label {
    font-size: 0.65rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  #apiKeyInput {
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    padding: 0.5rem 0.9rem;
    border-radius: 6px;
    width: 280px;
    transition: border-color 0.2s;
    outline: none;
  }
  #apiKeyInput:focus { border-color: var(--accent); }
  #apiKeyInput::placeholder { color: var(--muted); }

  /* ── Main layout ── */
  main {
    display: grid;
    grid-template-columns: 300px 1fr 340px;
    height: calc(100vh - 73px);
    overflow: hidden;
  }

  /* ── Panel base ── */
  .panel {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    padding: 1rem 1.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .badge {
    background: var(--surface2);
    color: var(--accent);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 0.15rem 0.6rem;
    font-size: 0.6rem;
    letter-spacing: 0.05em;
  }

  /* ── File list ── */
  .file-list {
    overflow-y: auto;
    flex: 1;
    padding: 0.5rem;
  }
  .file-list::-webkit-scrollbar { width: 4px; }
  .file-list::-webkit-scrollbar-track { background: transparent; }
  .file-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .file-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s;
    border: 1px solid transparent;
  }
  .file-item:hover { background: var(--surface2); }
  .file-item.active {
    background: var(--surface2);
    border-color: var(--accent);
  }
  .file-thumb {
    width: 40px; height: 40px;
    border-radius: 4px;
    object-fit: cover;
    background: var(--border);
    flex-shrink: 0;
  }
  .file-thumb-placeholder {
    width: 40px; height: 40px;
    border-radius: 4px;
    background: var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
    flex-shrink: 0;
  }
  .file-info { flex: 1; min-width: 0; }
  .file-name {
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text);
  }
  .file-ext {
    font-size: 0.62rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .file-item.active .file-name { color: var(--accent); }

  /* ── Center panel ── */
  .center-panel {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .preview-area {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
    position: relative;
    overflow: hidden;
  }
  .preview-area::before {
    content: '';
    position: absolute; inset: 0;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.3;
  }
  #previewImg {
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
    border-radius: 6px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6);
    position: relative;
    z-index: 1;
    display: none;
  }
  .preview-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    color: var(--muted);
    position: relative;
    z-index: 1;
  }
  .preview-placeholder .icon {
    font-size: 3rem;
    opacity: 0.3;
  }
  .preview-placeholder p {
    font-size: 0.75rem;
    letter-spacing: 0.05em;
  }

  .prompt-area {
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    height: 220px;
  }
  .prompt-area .panel-header {
    border-bottom: 1px solid var(--border);
  }
  #promptInput {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    line-height: 1.6;
    padding: 0.9rem 1.5rem;
    resize: none;
    outline: none;
  }
  #promptInput::placeholder { color: var(--muted); }

  .action-bar {
    padding: 0.9rem 1.5rem;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-shrink: 0;
  }
  .btn-analyze {
    background: var(--accent);
    color: #000;
    border: none;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.7rem 1.8rem;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .btn-analyze:hover { background: #d9ff55; transform: translateY(-1px); }
  .btn-analyze:active { transform: translateY(0); }
  .btn-analyze:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
  .btn-reset {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    padding: 0.7rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-reset:hover { border-color: var(--muted); color: var(--text); }

  .status-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--muted);
    flex-shrink: 0;
  }
  .status-dot.active { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
  .status-text { font-size: 0.65rem; color: var(--muted); }

  /* ── Results panel ── */
  .results-panel {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .results-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
  }
  .results-scroll::-webkit-scrollbar { width: 4px; }
  .results-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .empty-results {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 0.75rem;
    color: var(--muted);
  }
  .empty-results .icon { font-size: 2.5rem; opacity: 0.2; }
  .empty-results p { font-size: 0.7rem; letter-spacing: 0.05em; }

  /* ── Result cards ── */
  .result-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.75rem;
    animation: slideIn 0.3s ease;
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .result-card.error { border-color: var(--danger); }
  .result-card.ok    { border-color: var(--ok); }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  .card-type {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
  }
  .card-type .type-icon { font-size: 1.2rem; }
  .status-pill {
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.25rem 0.7rem;
    border-radius: 20px;
    border: 1px solid;
  }
  .status-pill.ok    { color: var(--ok);     border-color: var(--ok);     background: rgba(77,255,145,0.08); }
  .status-pill.nok   { color: var(--danger); border-color: var(--danger); background: rgba(255,77,77,0.08); }
  .status-pill.error { color: var(--danger); border-color: var(--danger); background: rgba(255,77,77,0.08); }

  .card-name {
    font-family: 'Syne', sans-serif;
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    color: var(--text);
  }
  .card-name.error-name { color: var(--danger); }
  .card-desc {
    font-size: 0.72rem;
    color: var(--muted);
    line-height: 1.6;
  }

  /* ── JSON view ── */
  .json-toggle {
    margin-top: 0.6rem;
    font-size: 0.62rem;
    color: var(--muted);
    cursor: pointer;
    text-decoration: underline;
    background: none;
    border: none;
    padding: 0;
    font-family: 'DM Mono', monospace;
  }
  .json-toggle:hover { color: var(--accent); }
  .json-block {
    display: none;
    margin-top: 0.6rem;
    background: #000;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
    font-size: 0.65rem;
    line-height: 1.6;
    color: #7ec8e3;
    white-space: pre-wrap;
    word-break: break-all;
    overflow-x: auto;
  }
  .json-block.visible { display: block; }

  /* ── Spinner ── */
  .spinner {
    display: none;
    width: 16px; height: 16px;
    border: 2px solid rgba(0,0,0,0.3);
    border-top-color: #000;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Loading overlay ── */
  #loadingOverlay {
    display: none;
    position: absolute; inset: 0;
    background: rgba(10,10,10,0.7);
    z-index: 10;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 1rem;
    backdrop-filter: blur(4px);
    border-radius: 0;
  }
  #loadingOverlay.visible { display: flex; }
  .loading-ring {
    width: 48px; height: 48px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  .loading-text {
    font-size: 0.7rem;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  /* ── Scrollbar global ── */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* ── No files message ── */
  .no-files {
    padding: 2rem 1rem;
    text-align: center;
    font-size: 0.72rem;
    color: var(--muted);
    line-height: 1.8;
  }
</style>
</head>
<body>

<header>
  <div class="logo-mark">BA</div>
  <div>
    <div class="header-title">Beverage Analyzer</div>
    <div class="header-sub">Gemma Vision · Dataset Inspector</div>
  </div>
  <div class="api-config">
    <span class="api-label">API Key</span>
    <input type="password" id="apiKeyInput" placeholder="Introduce tu API Key de Google..." />
  </div>
</header>

<main>

  <!-- ── Panel 1: File list ── -->
  <div class="panel">
    <div class="panel-header">
      Dataset
      <span class="badge" id="fileCount">0 archivos</span>
    </div>
    <div class="file-list" id="fileList">
      <div class="no-files">Cargando imágenes<br>de ./dataset…</div>
    </div>
  </div>

  <!-- ── Panel 2: Preview + Prompt ── -->
  <div class="center-panel">
    <div class="preview-area" id="previewArea">
      <div id="loadingOverlay">
        <div class="loading-ring"></div>
        <div class="loading-text">Analizando imagen…</div>
      </div>
      <div class="preview-placeholder" id="previewPlaceholder">
        <div class="icon">🖼️</div>
        <p>Selecciona una imagen del dataset</p>
      </div>
      <img id="previewImg" alt="Preview" />
    </div>

    <div class="prompt-area">
      <div class="panel-header">
        Prompt
        <span class="badge">editable</span>
      </div>
      <textarea id="promptInput" placeholder="Escribe o edita el prompt aquí…"></textarea>
    </div>

    <div class="action-bar">
      <button class="btn-analyze" id="analyzeBtn" disabled>
        <span class="spinner" id="btnSpinner"></span>
        <span id="btnText">Analizar</span>
      </button>
      <button class="btn-reset" onclick="resetPrompt()">Resetear prompt</button>
      <div class="status-dot" id="statusDot"></div>
      <span class="status-text" id="statusText">Selecciona una imagen</span>
    </div>
  </div>

  <!-- ── Panel 3: Results ── -->
  <div class="results-panel">
    <div class="panel-header">
      Resultados
      <span class="badge" id="resultCount">—</span>
    </div>
    <div class="results-scroll" id="resultsScroll">
      <div class="empty-results">
        <div class="icon">📊</div>
        <p>Los resultados aparecerán aquí</p>
      </div>
    </div>
  </div>

</main>

<script>
const DEFAULT_PROMPT = {{ default_prompt | tojson }};
let selectedFile = null;

document.getElementById('promptInput').value = DEFAULT_PROMPT;

// ── Load file list ──────────────────────────────────────────────────────────
async function loadFiles() {
  try {
    const res = await fetch('/api/files');
    const data = await res.json();
    const list = document.getElementById('fileList');
    const count = document.getElementById('fileCount');

    if (!data.files || data.files.length === 0) {
      list.innerHTML = '<div class="no-files">No se encontraron imágenes<br>en ./dataset</div>';
      count.textContent = '0 archivos';
      return;
    }

    count.textContent = `${data.files.length} archivo${data.files.length !== 1 ? 's' : ''}`;
    list.innerHTML = '';

    data.files.forEach(file => {
      const item = document.createElement('div');
      item.className = 'file-item';
      item.dataset.filename = file;

      const ext = file.split('.').pop().toUpperCase();
      const thumb = document.createElement('img');
      thumb.className = 'file-thumb';
      thumb.src = `/api/thumbnail/${encodeURIComponent(file)}`;
      thumb.alt = file;
      thumb.onerror = function() {
        this.style.display = 'none';
        const ph = document.createElement('div');
        ph.className = 'file-thumb-placeholder';
        ph.textContent = '🖼️';
        item.insertBefore(ph, item.firstChild);
      };

      const info = document.createElement('div');
      info.className = 'file-info';
      info.innerHTML = `<div class="file-name">${file}</div><div class="file-ext">${ext}</div>`;

      item.appendChild(thumb);
      item.appendChild(info);
      item.addEventListener('click', () => selectFile(file, item));
      list.appendChild(item);
    });
  } catch(e) {
    document.getElementById('fileList').innerHTML =
      '<div class="no-files">Error cargando archivos.<br>¿Está el servidor activo?</div>';
  }
}

// ── Select file ─────────────────────────────────────────────────────────────
function selectFile(filename, el) {
  document.querySelectorAll('.file-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');
  selectedFile = filename;

  const img = document.getElementById('previewImg');
  const placeholder = document.getElementById('previewPlaceholder');
  img.src = `/api/image/${encodeURIComponent(filename)}`;
  img.style.display = 'block';
  placeholder.style.display = 'none';

  document.getElementById('analyzeBtn').disabled = false;
  setStatus('Listo para analizar', true);
}

// ── Analyze ─────────────────────────────────────────────────────────────────
document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const apiKey = document.getElementById('apiKeyInput').value.trim();
  const prompt = document.getElementById('promptInput').value.trim();

  if (!selectedFile) return;
  if (!apiKey) {
    alert('Por favor, introduce tu API Key de Google.');
    document.getElementById('apiKeyInput').focus();
    return;
  }
  if (!prompt) {
    alert('El prompt no puede estar vacío.');
    return;
  }

  setBusy(true);
  setStatus('Analizando…', true);

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: selectedFile, api_key: apiKey, prompt })
    });

    const data = await res.json();

    if (data.error) {
      showError(data.error);
      setStatus('Error en el análisis', false);
    } else {
      renderResults(data.result, selectedFile);
      setStatus('Análisis completado', true);
    }
  } catch(e) {
    showError('Error de conexión con el servidor: ' + e.message);
    setStatus('Error de conexión', false);
  } finally {
    setBusy(false);
  }
});

// ── Render results ───────────────────────────────────────────────────────────
function renderResults(result, filename) {
  const scroll = document.getElementById('resultsScroll');
  const counter = document.getElementById('resultCount');
  scroll.innerHTML = '';

  if (!result || !result.objects) {
    scroll.innerHTML = '<div class="empty-results"><div class="icon">⚠️</div><p>Respuesta inesperada</p></div>';
    return;
  }

  const objects = result.objects;
  counter.textContent = `${objects.length} objeto${objects.length !== 1 ? 's' : ''}`;

  // File header
  const hdr = document.createElement('div');
  hdr.style.cssText = 'font-size:0.65rem;color:var(--muted);margin-bottom:0.75rem;letter-spacing:0.05em;';
  hdr.textContent = `📁 ${filename}`;
  scroll.appendChild(hdr);

  objects.forEach((obj, i) => {
    const isError = obj.type === 'ERROR' || obj.name === 'ERROR';
    const isOk    = obj.status === 'OK';
    const typeIcon = obj.type === 'BOTTLE' ? '🍾' : obj.type === 'CAN' ? '🥫' : '❌';

    const card = document.createElement('div');
    card.className = `result-card ${isError ? 'error' : isOk ? 'ok' : ''}`;

    const statusClass = isError ? 'error' : isOk ? 'ok' : 'nok';
    const statusLabel = isError ? 'ERROR' : isOk ? 'OK' : 'NO OK';

    card.innerHTML = `
      <div class="card-top">
        <div class="card-type">
          <span class="type-icon">${typeIcon}</span>
          ${obj.type}
        </div>
        <span class="status-pill ${statusClass}">${statusLabel}</span>
      </div>
      <div class="card-name ${isError ? 'error-name' : ''}">${obj.name || 'N/A'}</div>
      <div class="card-desc">${obj.description || ''}</div>
      <button class="json-toggle" onclick="toggleJson(this)">Ver JSON raw</button>
      <pre class="json-block">${JSON.stringify(obj, null, 2)}</pre>
    `;
    scroll.appendChild(card);
  });

  // Full JSON
  const fullCard = document.createElement('div');
  fullCard.style.cssText = 'margin-top:0.5rem;';
  fullCard.innerHTML = `
    <button class="json-toggle" onclick="toggleJson(this)">Ver respuesta completa</button>
    <pre class="json-block">${JSON.stringify(result, null, 2)}</pre>
  `;
  scroll.appendChild(fullCard);
}

function toggleJson(btn) {
  const block = btn.nextElementSibling;
  block.classList.toggle('visible');
  btn.textContent = block.classList.contains('visible') ? 'Ocultar JSON' : 'Ver JSON raw';
}

// ── Error display ─────────────────────────────────────────────────────────────
function showError(msg) {
  const scroll = document.getElementById('resultsScroll');
  document.getElementById('resultCount').textContent = 'error';
  scroll.innerHTML = `
    <div class="result-card error">
      <div class="card-top">
        <div class="card-type"><span class="type-icon">⚠️</span>ERROR</div>
        <span class="status-pill error">FAILED</span>
      </div>
      <div class="card-name error-name">Error en la solicitud</div>
      <div class="card-desc">${msg}</div>
    </div>`;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(text, active) {
  document.getElementById('statusText').textContent = text;
  document.getElementById('statusDot').className = `status-dot${active ? ' active' : ''}`;
}

function setBusy(busy) {
  document.getElementById('analyzeBtn').disabled = busy;
  document.getElementById('btnSpinner').style.display = busy ? 'block' : 'none';
  document.getElementById('btnText').textContent = busy ? 'Analizando…' : 'Analizar';
  document.getElementById('loadingOverlay').className = busy ? 'visible' : '';
}

function resetPrompt() {
  document.getElementById('promptInput').value = DEFAULT_PROMPT;
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadFiles();
</script>
</body>
</html>
"""


def compress_image(image_path: str) -> tuple[bytes, str]:
    img = Image.open(image_path)
    if img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail(MAX_SIZE, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), "image/jpeg"


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


@app.route("/")
def index():
    return render_template_string(HTML, default_prompt=DEFAULT_PROMPT)


@app.route("/api/files")
def list_files():
    if not DATASET_DIR.exists():
        return jsonify({"files": [], "error": "Carpeta ./dataset no encontrada"})
    files = sorted([
        f.name for f in DATASET_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ])
    return jsonify({"files": files})


@app.route("/api/image/<filename>")
def serve_image(filename):
    return send_from_directory(str(DATASET_DIR.absolute()), filename)


@app.route("/api/thumbnail/<filename>")
def serve_thumbnail(filename):
    path = DATASET_DIR / filename
    if not path.exists():
        return "", 404
    img = Image.open(str(path))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    img.thumbnail((80, 80), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=60)
    buf.seek(0)
    from flask import Response
    return Response(buf.getvalue(), mimetype="image/jpeg")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    filename = data.get("filename", "")
    api_key = data.get("api_key", "").strip()
    prompt = data.get("prompt", DEFAULT_PROMPT)

    if not api_key:
        return jsonify({"error": "API Key no proporcionada"}), 400

    image_path = DATASET_DIR / filename
    if not image_path.exists():
        return jsonify({"error": f"Archivo no encontrado: {filename}"}), 404

    try:
        jpeg_bytes, media_type = compress_image(str(image_path))
    except Exception as e:
        return jsonify({"error": f"Error procesando imagen: {e}"}), 500

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemma-3-27b-it:generateContent?key=" + api_key
    )

    image_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": media_type, "data": image_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.1, "topP": 0.95, "maxOutputTokens": 512},
    }

    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                             json=payload, timeout=60)
        resp.raise_for_status()
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP de la API: {e.response.status_code} — {e.response.text}"}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Error de red: {e}"}), 502

    api_resp = resp.json()
    try:
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        return jsonify({"error": "Respuesta inesperada de la API", "raw": api_resp}), 502

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.strip().upper() == "ERROR":
        result = {"objects": [{"type": "ERROR", "name": "ERROR", "status": "NO OK",
                                "description": "No se identificó ninguna bebida."}]}
    else:
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return jsonify({"error": f"No se pudo parsear el JSON de la respuesta:\n{text}"}), 502

    return jsonify({"result": result})


if __name__ == "__main__":
    print("\n🍾  Beverage Analyzer — Interfaz web")
    print("─" * 40)
    if not DATASET_DIR.exists():
        print(f"⚠️  Carpeta '{DATASET_DIR}' no encontrada. Créala y añade imágenes.")
        DATASET_DIR.mkdir(exist_ok=True)
    print(f"📁  Dataset: {DATASET_DIR.absolute()}")
    print(f"🌐  Abre en tu navegador: http://localhost:5000")
    print("─" * 40 + "\n")
    app.run(debug=False, port=5000)
