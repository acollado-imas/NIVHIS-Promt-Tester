#!/usr/bin/env python3
"""
Servidor Flask para la interfaz de análisis de bebidas.
Incluye análisis individual, batch con progreso en tiempo real y dashboard de resultados.
"""

import base64
import json
from io import BytesIO
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template_string, request, send_from_directory
from PIL import Image

app = Flask(__name__)

DATASET_DIR = Path("./dataset")
MAX_SIZE = (512, 512)
JPEG_QUALITY = 70

DEFAULT_PROMPT = (
    "Identifica la bebida de la imagen. "
    "Quiero una respuesta en formato json siguiendo el siguiente esquema:\n"
    '{\n  "objects": [\n    {\n'
    '      "type": "BOTTLE | CAN | ERROR",\n'
    '      "name": "BRAND NAME | ERROR",\n'
    '      "status": "OK | NO OK",\n'
    '      "description": "DESCRIPCION CORTA CON DATOS CURIOSOS SOBRE LA BEBIDA Y LA TEMPERATURA IDEAL DE CONSUMICION"\n'
    '    }\n  ]\n}\n'
    "Si no encuentras el nombre de la marca (o parte de el) o no encuentras el logo (o parte de el), "
    "y por lo tanto no estas 100% seguro de la marca, responde el 'name' con ERROR. "
    "No es admisible que el nombre de la marca detectada sea erroneo, es preferible responder con un error a la minima duda. "
    "Aunque haya mas de una bebida en la misma imagen y sean parecidas, no puedes asumir la marca de ninguna de las dos si no estas seguro.\n"
    "Si no hay ninguna bebida, responde ERROR.\n"
    "Envuelve el JSON final entre las etiquetas <result> y </result>. "
    "Ejemplo: <result>{...}</result>\n"
    "NO incluyas razonamiento, explicaciones ni texto adicional fuera de las etiquetas."
)

# ─── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NIVHIS Prompt Trainer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0a0a; --surface:#111; --surface2:#1a1a1a; --surface3:#222;
    --border:#2a2a2a; --accent:#c8f542; --accent-h:#d9ff55; --text:#f0f0f0;
    --muted:#666; --danger:#ff4d4d; --ok:#4dff91; --warn:#ffb84d;
  }
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;
    height:100vh;display:grid;grid-template-rows:auto auto 1fr;overflow:hidden}

  /* Header */
  header{border-bottom:1px solid var(--border);padding:0 2rem;display:flex;
    align-items:stretch;gap:0;background:var(--surface);flex-shrink:0;height:56px}
  .logo-wrap{display:flex;align-items:center;padding-right:1.75rem;
    border-right:1px solid var(--border);margin-right:1.5rem}
  .logo-wrap img{height:22px;width:auto;display:block;filter:brightness(0) invert(1)}
  .header-divider{width:1px;background:var(--border);margin:0}
  .h-app{display:flex;flex-direction:column;justify-content:center;gap:.15rem}
  .h-title{font-family:'Inter',sans-serif;font-size:.82rem;font-weight:600;
    letter-spacing:.02em;color:var(--text)}
  .h-sub{font-size:.58rem;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}
  .h-badge{display:inline-flex;align-items:center;gap:.3rem;background:rgba(200,245,66,.1);
    border:1px solid rgba(200,245,66,.25);color:var(--accent);border-radius:4px;
    font-size:.55rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
    padding:.15rem .5rem;margin-top:.1rem;width:fit-content}
  .h-badge::before{content:'';width:5px;height:5px;border-radius:50%;
    background:var(--accent);flex-shrink:0}
  .api-wrap{margin-left:auto;display:flex;align-items:center;gap:.65rem}
  .api-lbl{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
  #apiKey{background:var(--surface2);border:1px solid var(--border);color:var(--text);
    font-family:'DM Mono',monospace;font-size:.75rem;padding:.4rem .8rem;
    border-radius:6px;width:250px;outline:none;transition:border-color .2s}
  #apiKey:focus{border-color:var(--accent)}
  #apiKey::placeholder{color:var(--muted)}

  /* Tab bar */
  .tabs{display:flex;border-bottom:1px solid var(--border);background:var(--surface);
    padding:0 2rem;flex-shrink:0}
  .tab{padding:.6rem 1.3rem;font-size:.65rem;font-weight:600;letter-spacing:.08em;
    text-transform:uppercase;cursor:pointer;border-bottom:2px solid transparent;
    color:var(--muted);transition:all .15s;user-select:none;display:flex;align-items:center;gap:.45rem;
    font-family:'Inter',sans-serif}
  .tab:hover{color:var(--text)}
  .tab.active{color:var(--accent);border-bottom-color:var(--accent)}
  .tbadge{background:var(--surface2);color:var(--muted);border:1px solid var(--border);
    border-radius:20px;padding:.1rem .45rem;font-size:.55rem}
  .tab.active .tbadge{color:var(--accent);border-color:var(--accent)}

  /* Views */
  .view{display:none;height:100%;overflow:hidden}
  .view.active{display:grid}
  #v-single{grid-template-columns:270px 1fr 310px}
  #v-batch{grid-template-columns:1fr 370px}

  /* Panel */
  .panel{border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
  .ph{padding:.8rem 1.2rem .65rem;border-bottom:1px solid var(--border);font-size:.6rem;
    font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
    display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
    font-family:'Inter',sans-serif}
  .badge{background:var(--surface2);color:var(--accent);border:1px solid var(--border);
    border-radius:20px;padding:.1rem .5rem;font-size:.56rem;letter-spacing:.05em}

  /* File list */
  .flist{overflow-y:auto;flex:1;padding:.35rem}
  .flist::-webkit-scrollbar{width:3px}
  .flist::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .fi{display:flex;align-items:center;gap:.6rem;padding:.45rem .6rem;
    border-radius:6px;cursor:pointer;transition:background .12s;border:1px solid transparent}
  .fi:hover{background:var(--surface2)}
  .fi.active{background:var(--surface2);border-color:var(--accent)}
  .fthumb{width:34px;height:34px;border-radius:4px;object-fit:cover;background:var(--border);flex-shrink:0}
  .fph{width:34px;height:34px;border-radius:4px;background:var(--border);
    display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0}
  .finfo{flex:1;min-width:0}
  .fname{font-size:.7rem;font-weight:500;white-space:nowrap;overflow:hidden;
    text-overflow:ellipsis;color:var(--text)}
  .fext{font-size:.58rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .fi.active .fname{color:var(--accent)}
  .fdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
  .fdot.ok{background:var(--ok)}
  .fdot.error{background:var(--danger)}
  .fdot.nok{background:var(--warn)}

  /* Center single */
  .cpanel{border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
  .prev-area{flex:1;display:flex;align-items:center;justify-content:center;
    background:var(--bg);position:relative;overflow:hidden}
  .prev-area::before{content:'';position:absolute;inset:0;
    background-image:linear-gradient(var(--border) 1px,transparent 1px),
      linear-gradient(90deg,var(--border) 1px,transparent 1px);
    background-size:40px 40px;opacity:.22}
  #prevImg{max-width:90%;max-height:90%;object-fit:contain;border-radius:6px;
    box-shadow:0 20px 60px rgba(0,0,0,.6);position:relative;z-index:1;display:none}
  .prev-ph{display:flex;flex-direction:column;align-items:center;gap:.6rem;
    color:var(--muted);position:relative;z-index:1}
  .prev-ph .ico{font-size:2.2rem;opacity:.2}
  .prev-ph p{font-size:.7rem;letter-spacing:.05em}
  #loadOv{display:none;position:absolute;inset:0;background:rgba(10,10,10,.75);
    z-index:10;align-items:center;justify-content:center;flex-direction:column;
    gap:1rem;backdrop-filter:blur(4px)}
  #loadOv.on{display:flex}
  .ring{width:42px;height:42px;border:3px solid var(--border);
    border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
  .rtxt{font-size:.65rem;color:var(--muted);letter-spacing:.1em;text-transform:uppercase}

  .prompt-box{border-top:1px solid var(--border);display:flex;flex-direction:column;
    flex-shrink:0;height:190px}
  #promptTxt{flex:1;background:transparent;border:none;color:var(--text);
    font-family:'DM Mono',monospace;font-size:.68rem;line-height:1.6;
    padding:.75rem 1.2rem;resize:none;outline:none}
  #promptTxt::placeholder{color:var(--muted)}

  .abar{padding:.7rem 1.2rem;border-top:1px solid var(--border);
    display:flex;align-items:center;gap:.65rem;flex-shrink:0}
  .btn{border:none;font-family:'Inter',sans-serif;font-weight:600;font-size:.72rem;
    letter-spacing:.06em;text-transform:uppercase;padding:.55rem 1.3rem;border-radius:5px;
    cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:.4rem}
  .btn-p{background:var(--accent);color:#000}
  .btn-p:hover{background:var(--accent-h);transform:translateY(-1px)}
  .btn-p:active{transform:none}
  .btn-p:disabled{opacity:.4;cursor:not-allowed;transform:none}
  .btn-s{background:transparent;color:var(--muted);border:1px solid var(--border);
    font-family:'Inter',sans-serif;font-size:.65rem;padding:.55rem .85rem;border-radius:5px}
  .btn-s:hover{border-color:var(--muted);color:var(--text)}
  .btn-d{background:rgba(255,77,77,.1);color:var(--danger);border:1px solid rgba(255,77,77,.25);
    font-family:'Inter',sans-serif;font-size:.65rem;padding:.55rem .85rem;border-radius:5px}
  .btn-d:hover{background:rgba(255,77,77,.2)}
  .btn-d:disabled{opacity:.4;cursor:not-allowed}
  .sdot{width:6px;height:6px;border-radius:50%;background:var(--muted);flex-shrink:0}
  .sdot.on{background:var(--accent);box-shadow:0 0 6px var(--accent)}
  .stxt{font-size:.6rem;color:var(--muted)}

  /* Result cards */
  .rpanel{display:flex;flex-direction:column;overflow:hidden}
  .rscroll{flex:1;overflow-y:auto;padding:.8rem}
  .rscroll::-webkit-scrollbar{width:3px}
  .rscroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .empty-r{display:flex;flex-direction:column;align-items:center;justify-content:center;
    height:100%;gap:.6rem;color:var(--muted)}
  .empty-r .ico{font-size:2rem;opacity:.18}
  .empty-r p{font-size:.66rem;letter-spacing:.05em}
  .rcard{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
    padding:.85rem .95rem;margin-bottom:.6rem;animation:si .25s ease}
  @keyframes si{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
  .rcard.err{border-color:rgba(255,77,77,.4)}
  .rcard.ok{border-color:rgba(77,255,145,.35)}
  .rtop{display:flex;align-items:center;justify-content:space-between;margin-bottom:.6rem}
  .rtype{display:flex;align-items:center;gap:.4rem;font-size:.62rem;font-weight:500;
    text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
  .rtype .ti{font-size:1rem}
  .spill{font-size:.56rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
    padding:.18rem .55rem;border-radius:20px;border:1px solid}
  .spill.ok{color:var(--ok);border-color:var(--ok);background:rgba(77,255,145,.07)}
  .spill.nok{color:var(--warn);border-color:var(--warn);background:rgba(255,184,77,.07)}
  .spill.error{color:var(--danger);border-color:var(--danger);background:rgba(255,77,77,.07)}
  .rname{font-family:'Inter',sans-serif;font-size:1.05rem;font-weight:700;margin-bottom:.38rem}
  .rname.en{color:var(--danger)}
  .rdesc{font-size:.65rem;color:var(--muted);line-height:1.6}
  .jtog{margin-top:.45rem;font-size:.58rem;color:var(--muted);cursor:pointer;
    text-decoration:underline;background:none;border:none;padding:0;font-family:'DM Mono',monospace}
  .jtog:hover{color:var(--accent)}
  .jblk{display:none;margin-top:.45rem;background:#000;border:1px solid var(--border);
    border-radius:4px;padding:.6rem;font-size:.6rem;line-height:1.6;color:#7ec8e3;
    white-space:pre-wrap;word-break:break-all}
  .jblk.on{display:block}
  .spin{display:none;width:13px;height:13px;border:2px solid rgba(0,0,0,.3);
    border-top-color:#000;border-radius:50%;animation:spin .7s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .nofiles{padding:2rem 1rem;text-align:center;font-size:.68rem;color:var(--muted);line-height:1.8}

  /* ── BATCH ── */
  .bmain{display:flex;flex-direction:column;overflow:hidden;border-right:1px solid var(--border)}
  .bcontrols{padding:.9rem 1.4rem;border-bottom:1px solid var(--border);
    display:flex;align-items:flex-start;gap:1.1rem;flex-shrink:0;background:var(--surface)}
  .bpwrap{flex:1;display:flex;flex-direction:column;gap:.45rem}
  .bplbl{font-size:.58rem;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;
    font-family:'Inter',sans-serif;font-weight:600}
  #bPrompt{background:var(--surface2);border:1px solid var(--border);color:var(--text);
    font-family:'DM Mono',monospace;font-size:.68rem;line-height:1.55;
    padding:.6rem .85rem;border-radius:6px;resize:vertical;min-height:95px;
    max-height:170px;outline:none;transition:border-color .2s}
  #bPrompt:focus{border-color:var(--accent)}
  .bacts{display:flex;flex-direction:column;gap:.45rem;padding-top:1.3rem;min-width:150px}
  .delay-row{display:flex;align-items:center;gap:.45rem}
  .dlbl{font-size:.58rem;color:var(--muted);white-space:nowrap;font-family:'Inter',sans-serif;font-weight:500}
  #delayInp{width:50px;background:var(--surface2);border:1px solid var(--border);
    color:var(--text);font-family:'DM Mono',monospace;font-size:.7rem;
    padding:.3rem .45rem;border-radius:5px;outline:none;text-align:center}
  #delayInp:focus{border-color:var(--accent)}

  /* Progress */
  .bprog{padding:.65rem 1.4rem;border-bottom:1px solid var(--border);
    display:flex;align-items:center;gap:.9rem;flex-shrink:0}
  .ptrack{flex:1;height:3px;background:var(--border);border-radius:2px;overflow:hidden}
  .pfill{height:100%;background:var(--accent);border-radius:2px;width:0;transition:width .35s ease}
  .plbl{font-size:.62rem;color:var(--muted);white-space:nowrap;min-width:72px;text-align:right}
  .pstatus{font-size:.62rem;color:var(--muted);flex:1;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis}

  /* Batch grid */
  .bgscroll{flex:1;overflow-y:auto;padding:.9rem 1.1rem}
  .bgscroll::-webkit-scrollbar{width:3px}
  .bgscroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .bempty{display:flex;flex-direction:column;align-items:center;justify-content:center;
    height:100%;gap:.7rem;color:var(--muted)}
  .bempty .ico{font-size:2.8rem;opacity:.12}
  .bempty p{font-size:.7rem}
  .bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.65rem}

  .bc{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
    overflow:hidden;cursor:pointer;transition:border-color .15s,transform .15s;position:relative}
  .bc:hover{transform:translateY(-2px);border-color:var(--muted)}
  .bc.sel{border-color:var(--accent)!important}
  .bc.s-ok{border-color:rgba(77,255,145,.5)}
  .bc.s-error{border-color:rgba(255,77,77,.5)}
  .bc.s-nok{border-color:rgba(255,184,77,.5)}
  .bc.s-pending{opacity:.45}
  .bc.s-running{border-color:var(--accent)}
  .bcimg{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:var(--border)}
  .bcfoot{padding:.45rem .55rem;display:flex;align-items:center;justify-content:space-between;gap:.25rem}
  .bcname{font-size:.6rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
  .bcst{font-size:.58rem;font-weight:600;flex-shrink:0}
  .bcst.ok{color:var(--ok)} .bcst.error{color:var(--danger)}
  .bcst.nok{color:var(--warn)} .bcst.pending{color:var(--muted)} .bcst.running{color:var(--accent)}
  .bc-spinner{position:absolute;top:5px;right:5px;width:16px;height:16px;
    border:2px solid rgba(200,245,66,.25);border-top-color:var(--accent);
    border-radius:50%;animation:spin .7s linear infinite;display:none}
  .bc.s-running .bc-spinner{display:block}

  /* Batch detail */
  .bdetail{display:flex;flex-direction:column;overflow:hidden}
  .bdscroll{flex:1;overflow-y:auto;padding:.9rem}
  .bdscroll::-webkit-scrollbar{width:3px}
  .bdscroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .det-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
    height:100%;gap:.65rem;color:var(--muted)}
  .det-empty .ico{font-size:2.2rem;opacity:.13}
  .det-empty p{font-size:.65rem}
  .det-img{width:100%;aspect-ratio:16/9;background:var(--bg);border-radius:6px;
    overflow:hidden;margin-bottom:.7rem;display:flex;align-items:center;justify-content:center;
    border:1px solid var(--border)}
  .det-img img{max-width:100%;max-height:100%;object-fit:contain}
  .det-fn{font-size:.62rem;color:var(--muted);margin-bottom:.7rem;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

  /* Stats */
  .sbar{padding:.65rem .9rem;border-top:1px solid var(--border);
    display:flex;gap:.45rem;flex-shrink:0;flex-wrap:wrap;align-items:center}
  .schip{flex:1;min-width:55px;background:var(--surface2);border:1px solid var(--border);
    border-radius:6px;padding:.45rem .45rem .35rem;text-align:center}
  .sv{font-family:'Inter',sans-serif;font-size:1.1rem;font-weight:700;display:block}
  .sv.ok{color:var(--ok)} .sv.error{color:var(--danger)}
  .sv.nok{color:var(--warn)} .sv.total{color:var(--accent)}
  .sl{font-size:.52rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
  .expbtn{background:var(--surface2);border:1px solid var(--border);color:var(--muted);
    font-family:'DM Mono',monospace;font-size:.6rem;padding:.4rem .7rem;
    border-radius:6px;cursor:pointer;transition:all .15s;white-space:nowrap}
  .expbtn:hover{border-color:var(--accent);color:var(--accent)}
  /* Resolution toggle */
  .res-toggle{display:flex;align-items:center;gap:0;border:1px solid var(--border);
    border-radius:6px;overflow:hidden;flex-shrink:0}
  .res-btn{background:transparent;border:none;color:var(--muted);font-family:'Inter',sans-serif;
    font-size:.62rem;padding:.38rem .65rem;cursor:pointer;transition:all .15s;white-space:nowrap;
    border-right:1px solid var(--border);font-weight:500}
  .res-btn:last-child{border-right:none}
  .res-btn:hover{color:var(--text);background:var(--surface2)}
  .res-btn.active{background:var(--surface2);color:var(--accent)}
  /* Generation config panel */
  .gcfg-wrap{border-top:1px solid var(--border);flex-shrink:0}
  .gcfg-toggle{width:100%;background:none;border:none;color:var(--muted);
    font-family:'Inter',sans-serif;font-size:.6rem;font-weight:600;letter-spacing:.1em;
    text-transform:uppercase;padding:.55rem 1.2rem;cursor:pointer;text-align:left;
    display:flex;align-items:center;justify-content:space-between;transition:color .15s}
  .gcfg-toggle:hover{color:var(--text)}
  .gcfg-toggle .arr{transition:transform .2s;font-style:normal}
  .gcfg-toggle.open .arr{transform:rotate(180deg)}
  .gcfg-body{display:none;padding:.6rem 1.2rem .8rem;
    display:grid;grid-template-columns:1fr 1fr 1fr;gap:.65rem}
  .gcfg-body.hidden{display:none}
  .gcfg-field{display:flex;flex-direction:column;gap:.3rem}
  .gcfg-lbl{font-size:.56rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;
    font-family:'Inter',sans-serif;font-weight:600}
  .gcfg-inp{background:var(--surface2);border:1px solid var(--border);color:var(--text);
    font-family:'DM Mono',monospace;font-size:.72rem;padding:.35rem .55rem;
    border-radius:5px;outline:none;width:100%;transition:border-color .2s;text-align:center}
  .gcfg-inp:focus{border-color:var(--accent)}
  .gcfg-hint{font-size:.52rem;color:var(--muted)}
  /* Model selector */
  .model-wrap{display:flex;align-items:center;gap:.5rem;border-right:1px solid var(--border);
    padding-right:1.25rem;margin-right:.25rem}
  .model-lbl{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;
    white-space:nowrap}
  #providerSelect,#modelSelect{background:var(--surface2);border:1px solid var(--border);color:var(--text);
    font-family:'DM Mono',monospace;font-size:.72rem;padding:.38rem .65rem;
    border-radius:6px;outline:none;transition:border-color .2s;cursor:pointer}
  #providerSelect{max-width:130px}
  #modelSelect{max-width:240px}
  #providerSelect:focus,#modelSelect:focus{border-color:var(--accent)}
  #providerSelect option,#modelSelect option{background:var(--surface2);color:var(--text)}
</style>
</head>
<body>

<!-- Header -->
<header>
  <div class="logo-wrap">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 40" height="24" aria-label="i-mas">
      <text y="30" font-family="'Inter', 'Helvetica Neue', Arial, sans-serif"
            font-weight="700" font-size="30" letter-spacing="1" fill="#ffffff">i-mas</text>
      <rect x="0" y="35" width="75" height="2.5" fill="#c8f542"/>
    </svg>
  </div>
  <div class="h-app">
    <div class="h-title">NIVHIS Prompt Trainer</div>
    <div class="h-badge">Herramienta interna · AI Vision</div>
  </div>
  <div class="api-wrap">
    <div class="model-wrap">
      <span class="model-lbl">Proveedor</span>
      <select id="providerSelect" onchange="onProviderChange()">
        <option value="google">Google AI</option>
        <option value="groq">Groq</option>
        <option value="openrouter">OpenRouter</option>
      </select>
      <select id="modelSelect">
        <option value="gemma-4-31b-it">gemma-4-31b-it</option>
      </select>
      <button class="btn btn-s" onclick="listModels()" title="Cargar modelos disponibles">↺</button>
    </div>
    <span class="api-lbl">API Key</span>
    <input type="password" id="apiKey" placeholder="Introduce tu API Key…" />
  </div>
</header>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" onclick="switchTab('single')" id="tab-single">🔍 Individual</div>
  <div class="tab" onclick="switchTab('batch')" id="tab-batch">
    ⚡ Batch <span class="tbadge" id="batchBadge">0</span>
  </div>
</div>

<!-- ════ VIEW: SINGLE ════ -->
<div class="view active" id="v-single">

  <div class="panel">
    <div class="ph">Dataset <span class="badge" id="fileCount">0</span>
      <button onclick="loadFiles()" id="reloadBtn" title="Recargar lista" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:.85rem;padding:0;line-height:1;transition:color .15s" onmouseover="this.style.color='var(--accent)'" onmouseout="this.style.color='var(--muted)'">↺</button>
    </div>
    <div class="flist" id="fileList"><div class="nofiles">Cargando…</div></div>
  </div>

  <div class="cpanel">
    <div class="prev-area">
      <div id="loadOv">
        <div class="ring"></div>
        <div class="rtxt">Analizando imagen…</div>
      </div>
      <div class="prev-ph" id="prevPh">
        <div class="ico">🖼️</div>
        <p>Selecciona una imagen del dataset</p>
      </div>
      <img id="prevImg" alt="Preview" />
    </div>
    <div class="prompt-box">
      <div class="ph">Prompt <span class="badge">editable</span></div>
      <textarea id="promptTxt" placeholder="Escribe o edita el prompt aquí…"></textarea>
    </div>
    <div class="gcfg-wrap" id="gcfg-wrap-single">
      <button class="gcfg-toggle" onclick="toggleGcfg('single')">
        ⚙ Generation Config <span class="arr">▾</span>
      </button>
      <div class="gcfg-body hidden" id="gcfg-body-single">
        <div class="gcfg-field">
          <span class="gcfg-lbl">Temperature</span>
          <input class="gcfg-inp" type="number" id="s-temp" value="0.1" min="0" max="2" step="0.05">
          <span class="gcfg-hint">0 – 2</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Top P</span>
          <input class="gcfg-inp" type="number" id="s-topp" value="0.95" min="0" max="1" step="0.01">
          <span class="gcfg-hint">0 – 1</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Max Tokens</span>
          <input class="gcfg-inp" type="number" id="s-maxtok" value="1024" min="64" max="8192" step="64">
          <span class="gcfg-hint">64 – 8192</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Top K</span>
          <input class="gcfg-inp" type="number" id="s-topk" value="" min="1" max="100" step="1" placeholder="—">
          <span class="gcfg-hint">opcional</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Stop Sequence</span>
          <input class="gcfg-inp" type="text"   id="s-stop" value="" placeholder="—">
          <span class="gcfg-hint">opcional</span>
        </div>
      </div>
    </div>
    <div class="abar">
      <button class="btn btn-p" id="analyzeBtn" disabled>
        <span class="spin" id="btnSpin"></span>
        <span id="btnTxt">Analizar</span>
      </button>
      <button class="btn btn-s" onclick="resetPrompt()">Reset prompt</button>
      <div class="res-toggle">
        <button class="res-btn active" id="res512" onclick="setRes(512)">512px</button>
        <button class="res-btn"        id="res768" onclick="setRes(768)">768px</button>
      </div>
      <div class="sdot" id="sdot"></div>
      <span class="stxt" id="stxt">Selecciona una imagen</span>
    </div>
  </div>

  <div class="rpanel">
    <div class="ph">Resultados <span class="badge" id="rCount">—</span></div>
    <div class="rscroll" id="rScroll">
      <div class="empty-r"><div class="ico">📊</div><p>Los resultados aparecerán aquí</p></div>
    </div>
  </div>

</div>

<!-- ════ VIEW: BATCH ════ -->
<div class="view" id="v-batch">

  <div class="bmain">
    <!-- Controls -->
    <div class="bcontrols">
      <div class="bpwrap">
        <div class="bplbl">Prompt del batch</div>
        <textarea id="bPrompt" placeholder="Prompt…"></textarea>
      </div>
      <div class="bacts">
        <button class="btn btn-p" id="bStartBtn" onclick="startBatch()">
          <span class="spin" id="bSpin"></span>
          <span id="bBtnTxt">▶ Iniciar Batch</span>
        </button>
        <button class="btn btn-d" id="bStopBtn" onclick="stopBatch()" disabled>⏹ Detener</button>
        <button class="btn btn-s" onclick="clearBatch()">🗑 Limpiar</button>
        <div class="delay-row">
          <span class="dlbl">Delay (s)</span>
          <input type="number" id="delayInp" value="1" min="0" max="10" step="0.5" />
        </div>
        <div class="delay-row">
          <span class="dlbl">Resolución</span>
          <div class="res-toggle">
            <button class="res-btn active" id="bRes512" onclick="setBRes(512)">512px</button>
            <button class="res-btn"        id="bRes768" onclick="setBRes(768)">768px</button>
          </div>
        </div>
      </div>
    </div>
    <!-- Generation config for batch -->
    <div class="gcfg-wrap">
      <button class="gcfg-toggle" onclick="toggleGcfg('batch')">
        ⚙ Generation Config <span class="arr">▾</span>
      </button>
      <div class="gcfg-body hidden" id="gcfg-body-batch">
        <div class="gcfg-field">
          <span class="gcfg-lbl">Temperature</span>
          <input class="gcfg-inp" type="number" id="b-temp" value="0.1" min="0" max="2" step="0.05">
          <span class="gcfg-hint">0 – 2</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Top P</span>
          <input class="gcfg-inp" type="number" id="b-topp" value="0.95" min="0" max="1" step="0.01">
          <span class="gcfg-hint">0 – 1</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Max Tokens</span>
          <input class="gcfg-inp" type="number" id="b-maxtok" value="1024" min="64" max="8192" step="64">
          <span class="gcfg-hint">64 – 8192</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Top K</span>
          <input class="gcfg-inp" type="number" id="b-topk" value="" min="1" max="100" step="1" placeholder="—">
          <span class="gcfg-hint">opcional</span>
        </div>
        <div class="gcfg-field">
          <span class="gcfg-lbl">Stop Sequence</span>
          <input class="gcfg-inp" type="text"   id="b-stop" value="" placeholder="—">
          <span class="gcfg-hint">opcional</span>
        </div>
      </div>
    </div>

    <!-- Progress bar -->
    <div class="bprog" id="progRow" style="display:none">
      <span class="pstatus" id="pStatus">Iniciando…</span>
      <div class="ptrack"><div class="pfill" id="pFill"></div></div>
      <span class="plbl" id="pLbl">0 / 0</span>
    </div>

    <!-- Grid -->
    <div class="bgscroll">
      <div class="bempty" id="bEmpty"><div class="ico">⚡</div><p>Lanza el batch para ver los resultados</p></div>
      <div class="bgrid" id="bGrid" style="display:none"></div>
    </div>
  </div>

  <!-- Detail + Stats -->
  <div class="bdetail">
    <div class="ph">Detalle <span class="badge" id="detBadge">—</span></div>
    <div class="bdscroll" id="bDetail">
      <div class="det-empty"><div class="ico">👆</div><p>Haz click en una imagen para ver el resultado</p></div>
    </div>
    <div class="sbar">
      <div class="schip"><span class="sv total" id="sTotal">0</span><span class="sl">Total</span></div>
      <div class="schip"><span class="sv ok"    id="sOk">0</span><span class="sl">OK</span></div>
      <div class="schip"><span class="sv nok"   id="sNok">0</span><span class="sl">No OK</span></div>
      <div class="schip"><span class="sv error" id="sErr">0</span><span class="sl">Error</span></div>
      <button class="expbtn" onclick="exportResults()">⬇ Exportar JSON</button>
    </div>
  </div>

</div>

<script>
// ─── State ────────────────────────────────────────────────────────────────────
const DEFAULT_PROMPT = {{ default_prompt | tojson }};
let selectedFile = null;
let allFiles = [];
let batchResults = {};
let batchRunning = false;
let batchAbort = false;
let currentRes  = 512;   // single view resolution
let batchRes    = 512;   // batch view resolution

document.getElementById('promptTxt').value = DEFAULT_PROMPT;
document.getElementById('bPrompt').value   = DEFAULT_PROMPT;

function setRes(v) {
  currentRes = v;
  document.getElementById('res512').classList.toggle('active', v===512);
  document.getElementById('res768').classList.toggle('active', v===768);
}
function setBRes(v) {
  batchRes = v;
  document.getElementById('bRes512').classList.toggle('active', v===512);
  document.getElementById('bRes768').classList.toggle('active', v===768);
}
function toggleGcfg(view) {
  const body = document.getElementById('gcfg-body-'+view);
  const btn  = body.previousElementSibling;
  const open = body.classList.toggle('hidden');
  btn.classList.toggle('open', !open);
}
function getGenConfig(prefix) {
  const v = id => document.getElementById(prefix+'-'+id).value;
  const cfg = {
    temperature:     parseFloat(v('temp'))   || 0.1,
    topP:            parseFloat(v('topp'))   || 0.95,
    maxOutputTokens: parseInt(v('maxtok'))   || 512,
  };
  const topk = parseInt(v('topk'));
  if (topk > 0) cfg.topK = topk;
  const stop = v('stop').trim();
  if (stop) cfg.stopSequences = [stop];
  return cfg;
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function switchTab(t) {
  ['single','batch'].forEach(id => {
    document.getElementById('tab-'+id).classList.toggle('active', id===t);
    document.getElementById('v-'+id).classList.toggle('active', id===t);
  });
}

// ─── Load files ───────────────────────────────────────────────────────────────
async function loadFiles() {
  const btn = document.getElementById('reloadBtn');
  if (btn) { btn.style.animation='spin .6s linear infinite'; btn.style.display='inline-block'; }
  try {
    const r = await fetch('/api/files');
    const d = await r.json();
    allFiles = d.files || [];
    document.getElementById('fileCount').textContent = allFiles.length + ' archivos';
    document.getElementById('batchBadge').textContent = allFiles.length;
    buildFileList();
  } catch(e) {
    document.getElementById('fileList').innerHTML = '<div class="nofiles">Error cargando archivos.</div>';
  } finally {
    if (btn) { btn.style.animation=''; }
  }
}

function buildFileList() {
  const list = document.getElementById('fileList');
  if (!allFiles.length) { list.innerHTML = '<div class="nofiles">No hay imágenes en ./dataset</div>'; return; }
  list.innerHTML = '';
  allFiles.forEach(f => {
    const item = document.createElement('div');
    item.className = 'fi'; item.dataset.f = f;
    const ext = f.split('.').pop().toUpperCase();
    const img = document.createElement('img');
    img.className = 'fthumb';
    img.src = `/api/thumbnail/${encodeURIComponent(f)}`;
    img.onerror = function(){ this.style.display='none'; const p=document.createElement('div'); p.className='fph'; p.textContent='🖼️'; item.insertBefore(p,item.firstChild); };
    const info = document.createElement('div'); info.className = 'finfo';
    info.innerHTML = `<div class="fname">${f}</div><div class="fext">${ext}</div>`;
    const dot = document.createElement('div'); dot.className='fdot'; dot.id='fdot-'+f;
    item.append(img, info, dot);
    item.addEventListener('click', () => selectFile(f, item));
    list.appendChild(item);
  });
}

function setFileDot(f, cls) {
  const d = document.getElementById('fdot-'+f);
  if (d) d.className = 'fdot ' + cls;
}

// ─── Single ───────────────────────────────────────────────────────────────────
function selectFile(f, el) {
  document.querySelectorAll('.fi').forEach(i => i.classList.remove('active'));
  el.classList.add('active');
  selectedFile = f;
  document.getElementById('prevImg').src = `/api/image/${encodeURIComponent(f)}`;
  document.getElementById('prevImg').style.display = 'block';
  document.getElementById('prevPh').style.display = 'none';
  document.getElementById('analyzeBtn').disabled = false;
  setStatus('Listo para analizar', true);
}

document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const key    = document.getElementById('apiKey').value.trim();
  const prompt = document.getElementById('promptTxt').value.trim();
  if (!selectedFile) return;
  if (!key)    { alert('Introduce tu API Key.'); return; }
  if (!prompt) { alert('El prompt no puede estar vacío.'); return; }
  setBusy(true); setStatus('Analizando…', true);
  try {
    const d = await callAnalyze(selectedFile, key, prompt, currentRes, getGenConfig('s'));
    if (d.error) { showSingleErr(d.error); setStatus('Error', false); }
    else { renderSingle(d.result, selectedFile); setStatus('Completado ✓', true); }
  } catch(e) { showSingleErr('Error: '+e.message); setStatus('Error', false); }
  finally { setBusy(false); }
});

async function callAnalyze(filename, key, prompt, maxSize=512, genConfig=null) {
  const model = document.getElementById('modelSelect')?.value || 'gemma-4-31b-it';
  const r = await fetch('/api/analyze', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({filename, api_key:key, prompt, max_size:maxSize, gen_config: genConfig, model})
  });
  return r.json();
}

// ─── Batch ────────────────────────────────────────────────────────────────────
async function startBatch() {
  const key    = document.getElementById('apiKey').value.trim();
  const prompt = document.getElementById('bPrompt').value.trim();
  if (!key)           { alert('Introduce tu API Key.'); return; }
  if (!prompt)        { alert('El prompt no puede estar vacío.'); return; }
  if (!allFiles.length) { alert('No hay imágenes en ./dataset.'); return; }

  const delay = parseFloat(document.getElementById('delayInp').value) || 0;
  const bGenCfg = getGenConfig('b');
  batchRunning = true; batchAbort = false; batchResults = {};
  updateStats();

  document.getElementById('bStartBtn').disabled = true;
  document.getElementById('bSpin').style.display = 'block';
  document.getElementById('bBtnTxt').textContent = 'Ejecutando…';
  document.getElementById('bStopBtn').disabled = false;

  // Build grid
  const grid = document.getElementById('bGrid');
  grid.innerHTML = ''; grid.style.display = 'grid';
  document.getElementById('bEmpty').style.display = 'none';
  document.getElementById('progRow').style.display = 'flex';

  allFiles.forEach(f => {
    const c = document.createElement('div');
    c.className = 'bc s-pending'; c.id = 'bc-'+f;
    c.innerHTML = `<img class="bcimg" src="/api/thumbnail/${encodeURIComponent(f)}" alt="${f}">
      <div class="bc-spinner"></div>
      <div class="bcfoot"><span class="bcname">${f}</span>
      <span class="bcst pending" id="bcst-${f}">—</span></div>`;
    c.addEventListener('click', () => showDetail(f));
    grid.appendChild(c);
  });

  const total = allFiles.length;
  for (let i = 0; i < total; i++) {
    if (batchAbort) break;
    const f = allFiles[i];
    setCardState(f, 'running', '…');
    document.getElementById('pFill').style.width = `${(i/total)*100}%`;
    document.getElementById('pLbl').textContent  = `${i} / ${total}`;
    document.getElementById('pStatus').textContent = `Analizando: ${f}`;

    try {
      const d = await callAnalyze(f, key, prompt, batchRes, bGenCfg);
      if (d.error) {
        batchResults[f] = {state:'error', error:d.error, result:null};
        setCardState(f,'error','ERR'); setFileDot(f,'error');
      } else {
        const objs = d.result?.objects || [];
        const hasErr = objs.some(o => o.type==='ERROR'||o.name==='ERROR');
        const hasNok = objs.some(o => o.status==='NO OK');
        const st = hasErr ? 'error' : hasNok ? 'nok' : 'ok';
        const lb = hasErr ? 'ERR'   : hasNok ? 'NOK' : 'OK';
        batchResults[f] = {state:st, result:d.result, error:null};
        setCardState(f, st, lb); setFileDot(f, st);
      }
    } catch(e) {
      batchResults[f] = {state:'error', error:e.message, result:null};
      setCardState(f,'error','ERR'); setFileDot(f,'error');
    }
    updateStats();
    if (delay > 0 && i < total-1 && !batchAbort) await sleep(delay*1000);
  }

  const done = batchAbort ? 'Detenido' : 'Completado';
  const proc = Object.keys(batchResults).length;
  document.getElementById('pFill').style.width = `${(proc/total)*100}%`;
  document.getElementById('pLbl').textContent  = `${proc} / ${total}`;
  document.getElementById('pStatus').textContent = `${done} · ${proc} imágenes procesadas`;

  batchRunning = false;
  document.getElementById('bStartBtn').disabled = false;
  document.getElementById('bSpin').style.display = 'none';
  document.getElementById('bBtnTxt').textContent = '▶ Iniciar Batch';
  document.getElementById('bStopBtn').disabled = true;
}

function stopBatch() {
  batchAbort = true;
  document.getElementById('bStopBtn').disabled = true;
  document.getElementById('pStatus').textContent = 'Deteniendo…';
}

function clearBatch() {
  if (batchRunning) stopBatch();
  batchResults = {};
  document.getElementById('bGrid').innerHTML = '';
  document.getElementById('bGrid').style.display = 'none';
  document.getElementById('bEmpty').style.display = 'flex';
  document.getElementById('progRow').style.display = 'none';
  document.getElementById('bDetail').innerHTML = '<div class="det-empty"><div class="ico">👆</div><p>Haz click en una imagen para ver el resultado</p></div>';
  document.getElementById('detBadge').textContent = '—';
  updateStats();
  allFiles.forEach(f => setFileDot(f,''));
}

function setCardState(f, state, lbl) {
  const c = document.getElementById('bc-'+f);
  const s = document.getElementById('bcst-'+f);
  if (c) c.className = `bc s-${state}`;
  if (s) { s.className = `bcst ${state}`; s.textContent = lbl; }
}

function showDetail(f) {
  document.querySelectorAll('.bc').forEach(c => c.classList.remove('sel'));
  const bc = document.getElementById('bc-'+f);
  if (bc) bc.classList.add('sel');

  const data = batchResults[f];
  const scr  = document.getElementById('bDetail');
  document.getElementById('detBadge').textContent = f;

  if (!data) {
    scr.innerHTML = '<div class="det-empty"><div class="ico">⏳</div><p>Imagen no procesada aún</p></div>';
    return;
  }

  let html = `<div class="det-img"><img src="/api/image/${encodeURIComponent(f)}" alt="${f}"></div>
    <div class="det-fn">📁 ${esc(f)}</div>`;

  if (data.error) {
    html += card({type:'ERROR',name:'Error en la solicitud',status:'NO OK',description:data.error});
  } else {
    (data.result?.objects||[]).forEach(o => html += card(o));
    html += `<button class="jtog" onclick="toggleJ(this)">Ver respuesta completa</button>
      <pre class="jblk">${esc(JSON.stringify(data.result,null,2))}</pre>`;
  }
  scr.innerHTML = html;
}

function card(o) {
  const isErr  = o.type==='ERROR' || o.name==='ERROR';
  const isOk   = o.status==='OK';
  const icon   = o.type==='BOTTLE'?'🍾':o.type==='CAN'?'🥫':'❌';
  const sc     = isErr?'error':isOk?'ok':'nok';
  const sl     = isErr?'ERROR':isOk?'OK':'NO OK';
  return `<div class="rcard ${isErr?'err':isOk?'ok':''}">
    <div class="rtop">
      <div class="rtype"><span class="ti">${icon}</span>${esc(o.type)}</div>
      <span class="spill ${sc}">${sl}</span>
    </div>
    <div class="rname ${isErr?'en':''}">${esc(o.name||'N/A')}</div>
    <div class="rdesc">${esc(o.description||'')}</div>
    <button class="jtog" onclick="toggleJ(this)">Ver JSON raw</button>
    <pre class="jblk">${esc(JSON.stringify(o,null,2))}</pre>
  </div>`;
}

function updateStats() {
  const v = Object.values(batchResults);
  document.getElementById('sTotal').textContent = v.length;
  document.getElementById('sOk').textContent    = v.filter(x=>x.state==='ok').length;
  document.getElementById('sNok').textContent   = v.filter(x=>x.state==='nok').length;
  document.getElementById('sErr').textContent   = v.filter(x=>x.state==='error').length;
}

function exportResults() {
  const data = allFiles.map(f => ({
    filename: f,
    state:    batchResults[f]?.state  || 'pending',
    result:   batchResults[f]?.result || null,
    error:    batchResults[f]?.error  || null,
  }));
  const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a = Object.assign(document.createElement('a'),
    {href:URL.createObjectURL(blob), download:`batch_${Date.now()}.json`});
  a.click();
}

// ─── Single helpers ───────────────────────────────────────────────────────────
function renderSingle(result, f) {
  const scr = document.getElementById('rScroll');
  document.getElementById('rCount').textContent = (result?.objects||[]).length + ' obj';
  scr.innerHTML = `<div style="font-size:.6rem;color:var(--muted);margin-bottom:.6rem">📁 ${esc(f)}</div>`;
  (result?.objects||[]).forEach(o => { scr.insertAdjacentHTML('beforeend', card(o)); });
  scr.insertAdjacentHTML('beforeend',
    `<button class="jtog" onclick="toggleJ(this)">Ver respuesta completa</button>
     <pre class="jblk">${esc(JSON.stringify(result,null,2))}</pre>`);
}

function showSingleErr(msg) {
  document.getElementById('rCount').textContent = 'error';
  document.getElementById('rScroll').innerHTML = card({type:'ERROR',name:'Error',status:'NO OK',description:msg});
}

function toggleJ(btn) {
  const b = btn.nextElementSibling;
  b.classList.toggle('on');
  btn.textContent = b.classList.contains('on') ? 'Ocultar JSON' : 'Ver JSON raw';
}

function setStatus(t,a) {
  document.getElementById('stxt').textContent = t;
  document.getElementById('sdot').className = 'sdot'+(a?' on':'');
}
function setBusy(b) {
  document.getElementById('analyzeBtn').disabled = b;
  document.getElementById('btnSpin').style.display = b?'block':'none';
  document.getElementById('btnTxt').textContent = b?'Analizando…':'Analizar';
  document.getElementById('loadOv').className = b?'on':'';
}
function resetPrompt() {
  document.getElementById('promptTxt').value = DEFAULT_PROMPT;
  document.getElementById('bPrompt').value   = DEFAULT_PROMPT;
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

// Default models per provider
const PROVIDER_DEFAULTS = {
  google:      { model: 'gemma-4-31b-it',                      placeholder: 'API Key de Google AI Studio' },
  groq:        { model: 'meta-llama/llama-4-scout-17b-16e-instruct', placeholder: 'API Key de Groq (gsk_...)' },
  openrouter:  { model: 'qwen/qwen2.5-vl-72b-instruct:free',   placeholder: 'API Key de OpenRouter (sk-or-...)' },
};

function onProviderChange() {
  const provider = document.getElementById('providerSelect').value;
  const def = PROVIDER_DEFAULTS[provider];
  document.getElementById('apiKey').placeholder = def.placeholder;
  document.getElementById('modelSelect').innerHTML =
    `<option value="${def.model}">${def.model}</option>`;
}

async function listModels() {
  const key      = document.getElementById('apiKey').value.trim();
  const provider = document.getElementById('providerSelect').value;
  if (!key) { alert('Introduce tu API Key primero.'); return; }
  const btn = event.currentTarget;
  btn.style.animation = 'spin .6s linear infinite';
  btn.style.display = 'inline-block';
  try {
    const r = await fetch(`/api/models?key=${encodeURIComponent(key)}&provider=${provider}`);
    const d = await r.json();
    if (d.error) { alert('Error cargando modelos:\n' + d.error); return; }
    const sel     = document.getElementById('modelSelect');
    const current = sel.value;
    sel.innerHTML = '';
    d.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      if (m === current) opt.selected = true;
      sel.appendChild(opt);
    });
    if (!d.models.includes(current) && sel.options.length) sel.value = sel.options[0].value;
  } catch(e) {
    alert('Error de conexión: ' + e.message);
  } finally {
    btn.style.animation = '';
  }
}

async function callAnalyze(filename, key, prompt, maxSize=512, genConfig=null) {
  const model    = document.getElementById('modelSelect')?.value  || 'gemma-4-31b-it';
  const provider = document.getElementById('providerSelect')?.value || 'google';
  const r = await fetch('/api/analyze', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({filename, api_key:key, prompt, max_size:maxSize, gen_config:genConfig, model, provider})
  });
  return r.json();
}

loadFiles();
</script>
</body>
</html>
"""


# ─── Python helpers ────────────────────────────────────────────────────────────

def compress_image(image_path: str, max_size: tuple = MAX_SIZE) -> tuple[bytes, str]:
    img = Image.open(image_path)
    if img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), "image/jpeg"


def call_api(provider: str, api_key: str, jpeg_bytes: bytes, media_type: str,
             prompt: str, generation_config: dict | None = None,
             model: str = "gemma-4-31b-it") -> dict:
    """Unified API caller. Returns a normalised response dict with a 'candidates' key."""
    if generation_config is None:
        generation_config = {"temperature": 0.1, "topP": 0.95, "maxOutputTokens": 1024}

    image_b64 = base64.b64encode(jpeg_bytes).decode()

    if provider == "google":
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")
        payload = {
            "contents": [{"parts": [
                {"inline_data": {"mime_type": media_type, "data": image_b64}},
                {"text": prompt},
            ]}],
            "generationConfig": {
                "temperature":     generation_config.get("temperature", 0.1),
                "topP":            generation_config.get("topP", 0.95),
                "maxOutputTokens": generation_config.get("maxOutputTokens", 1024),
                **({} if "topK" not in generation_config else {"topK": generation_config["topK"]}),
                **({} if "stopSequences" not in generation_config else {"stopSequences": generation_config["stopSequences"]}),
            },
        }
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                             json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()  # already in Google format

    elif provider in ("groq", "openrouter"):
        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            "temperature": generation_config.get("temperature", 0.1),
            "top_p":       generation_config.get("topP", 0.95),
            "max_tokens":  generation_config.get("maxOutputTokens", 1024),
        }
        if "stopSequences" in generation_config:
            payload["stop"] = generation_config["stopSequences"]

        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://i-mas.com"
            headers["X-Title"]      = "NIVHIS Prompt Trainer"

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Normalise OpenAI format → Google format so parse_response works unchanged
        text = data["choices"][0]["message"]["content"]
        return {
            "candidates": [{
                "content": {
                    "parts": [{"text": text}],
                    "role": "model",
                }
            }]
        }

    else:
        raise ValueError(f"Proveedor desconocido: {provider}")


def parse_response(api_resp: dict) -> dict:
    parts = api_resp["candidates"][0]["content"]["parts"]

    # Keep only the part without "thought": true
    answer_parts = [p for p in parts if not p.get("thought", False)]
    text = "\n".join(p.get("text", "") for p in answer_parts).strip()

    print(f"📄  Texto de respuesta ({len(text)} chars):\n{text}")

    import re

    # 1. Extract from <result>...</result>
    tag_match = re.search(r"<result>\s*(.*?)\s*</result>", text, re.DOTALL)
    if tag_match:
        text = tag_match.group(1).strip()
        print("🔍  JSON extraído de etiquetas <result>")
    else:
        # 2. Extract from ```json ... ``` fence
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
            print("🔍  JSON extraído de bloque markdown")
        else:
            # 3. Extract by first { and last }
            start = text.find("{")
            end   = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end+1].strip()
                print("🔍  JSON extraído por posición de llaves")

    # 4. Plain ERROR text
    if text.strip().upper() == "ERROR":
        return {"objects": [{"type": "ERROR", "name": "ERROR", "status": "NO OK",
                              "description": "No se identificó ninguna bebida."}]}

    return json.loads(text)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML, default_prompt=DEFAULT_PROMPT)


@app.route("/api/files")
def list_files():
    if not DATASET_DIR.exists():
        return jsonify({"files": []})
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
    img.thumbnail((120, 120), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=65)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/jpeg")


@app.route("/api/models")
def list_models():
    api_key  = request.args.get("key", "").strip()
    provider = request.args.get("provider", "google").strip()
    if not api_key:
        return jsonify({"error": "API Key no proporcionada"}), 400
    try:
        if provider == "google":
            resp = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=15)
            resp.raise_for_status()
            data   = resp.json()
            models = [
                m["name"].replace("models/", "") for m in data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]

        elif provider == "groq":
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            resp.raise_for_status()
            data   = resp.json()
            # Keep only vision-capable models (those with vision in context or id)
            models = [m["id"] for m in data.get("data", [])]
            # Put vision models first
            models.sort(key=lambda m: (0 if "vision" in m or "llama-4" in m or "scout" in m or "maverick" in m else 1, m))

        elif provider == "openrouter":
            resp = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # Keep only multimodal/vision models and free ones
            models = [
                m["id"] for m in data.get("data", [])
                if any(mod in m.get("architecture", {}).get("modality", "") for mod in ["image", "vision", "multimodal"])
            ]
            models.sort()

        else:
            return jsonify({"error": f"Proveedor desconocido: {provider}"}), 400

        return jsonify({"models": models})

    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}: {e.response.text}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data     = request.get_json()
    filename = data.get("filename", "")
    api_key  = data.get("api_key", "").strip()
    prompt   = data.get("prompt", DEFAULT_PROMPT)
    max_size_val = int(data.get("max_size", 512))
    max_size_val = max_size_val if max_size_val in (512, 768) else 512
    max_size = (max_size_val, max_size_val)
    gen_config = data.get("gen_config") or {}
    model    = data.get("model",    "gemma-4-31b-it").strip() or "gemma-4-31b-it"
    provider = data.get("provider", "google").strip()         or "google"
    # Sanitise / apply defaults
    generation_config = {
        "temperature":     float(gen_config.get("temperature", 0.1)),
        "topP":            float(gen_config.get("topP", 0.95)),
        "maxOutputTokens": int(gen_config.get("maxOutputTokens", 1024)),
    }
    if "topK" in gen_config:
        generation_config["topK"] = int(gen_config["topK"])
    if gen_config.get("stopSequences"):
        generation_config["stopSequences"] = gen_config["stopSequences"]

    if not api_key:
        return jsonify({"error": "API Key no proporcionada"}), 400

    image_path = DATASET_DIR / filename
    if not image_path.exists():
        return jsonify({"error": f"Archivo no encontrado: {filename}"}), 404

    print(f"\n{'─'*50}")
    print(f"📸  Analizando  : {filename}")
    print(f"🤖  Proveedor   : {provider} / {model}")
    print(f"📐  Resolución  : {max_size_val}px")
    print(f"⚙️   Gen config  : {json.dumps(generation_config)}")

    try:
        jpeg_bytes, media_type = compress_image(str(image_path), max_size)
        print(f"🗜️   Imagen JPEG : {len(jpeg_bytes):,} bytes")
    except Exception as e:
        print(f"❌  Error comprimiendo imagen: {e}")
        return jsonify({"error": f"Error procesando imagen: {e}"}), 500

    try:
        print(f"🌐  Llamando a la API...")
        api_resp = call_api(provider, api_key, jpeg_bytes, media_type, prompt, generation_config, model)
        print(f"✅  Respuesta recibida:")
        print(json.dumps(api_resp, indent=2, ensure_ascii=False))
    except requests.HTTPError as e:
        print(f"❌  Error HTTP {e.response.status_code}:")
        print(e.response.text)
        return jsonify({"error": f"Error HTTP {e.response.status_code}: {e.response.text}"}), 502
    except requests.RequestException as e:
        print(f"❌  Error de red: {e}")
        return jsonify({"error": f"Error de red: {e}"}), 502

    try:
        result = parse_response(api_resp)
        print(f"✅  JSON parseado correctamente")
        print(f"{'─'*50}\n")
    except Exception as e:
        raw = ""
        try:
            raw = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            pass
        print(f"❌  Error parseando respuesta: {e}")
        print(f"📄  Texto raw del modelo:\n{raw}")
        print(f"{'─'*50}\n")
        return jsonify({"error": f"No se pudo parsear la respuesta: {e}", "raw_text": raw}), 502

    return jsonify({"result": result})


if __name__ == "__main__":
    print("\n🍾  NIVHIS Prompt Trainer — Interfaz web")
    print("─" * 40)
    if not DATASET_DIR.exists():
        DATASET_DIR.mkdir(exist_ok=True)
        print("⚠️  Carpeta './dataset' creada. Añade imágenes.")
    print(f"📁  Dataset : {DATASET_DIR.absolute()}")
    print(f"🌐  URL     : http://localhost:5000")
    print("─" * 40 + "\n")
    app.run(debug=False, port=5000, threaded=True)