# NIVHIS Prompt Trainer — CLAUDE.md

Herramienta interna de i-mas para evaluar y afinar prompts de visión artificial sobre un dataset de imágenes de bebidas, usando el modelo **Gemma 3 27B** a través de la API de Google Generative Language.

---

## Estructura del proyecto

```
./
├── server.py          # Servidor Flask + toda la UI (HTML/CSS/JS incrustados)
├── requirements.txt   # Dependencias Python
└── dataset/           # Carpeta con las imágenes a analizar (no incluida en repo)
```

Todo el frontend (HTML, CSS, JavaScript) está incrustado como una cadena de texto dentro de `server.py`. No hay ficheros separados de frontend.

---

## Arranque

```bash
pip install -r requirements.txt
python server.py
# → http://localhost:5000
```

La carpeta `./dataset` se crea automáticamente si no existe. Coloca ahí las imágenes antes de arrancar (o recarga la lista desde la UI con el botón ↺).

---

## Dependencias

```
flask>=3.0
requests>=2.31
Pillow>=10.0
```

---

## Arquitectura

### Backend (`server.py`)

**Constantes globales:**
- `DATASET_DIR = Path("./dataset")` — directorio de imágenes
- `MAX_SIZE = (512, 512)` — resolución de compresión por defecto
- `JPEG_QUALITY = 70` — calidad JPEG de compresión
- `DEFAULT_PROMPT` — prompt base en español para identificación de bebidas

**Funciones principales:**

| Función | Descripción |
|---|---|
| `compress_image(path, max_size)` | Convierte cualquier imagen a JPEG, redimensiona a max_size manteniendo aspect ratio, aplica calidad 70 |
| `call_gemma(api_key, jpeg_bytes, media_type, prompt, generation_config)` | Llama a la API de Gemma con la imagen en base64 y devuelve el JSON crudo |
| `parse_response(api_resp)` | Extrae el texto de la respuesta, limpia fences de markdown y parsea el JSON |

**Rutas Flask:**

| Ruta | Método | Descripción |
|---|---|---|
| `/` | GET | Sirve el HTML de la aplicación |
| `/api/files` | GET | Lista las imágenes en `./dataset` |
| `/api/image/<filename>` | GET | Sirve la imagen original |
| `/api/thumbnail/<filename>` | GET | Sirve una miniatura 120×120px |
| `/api/analyze` | POST | Analiza una imagen con el modelo Gemma |

**Payload de `/api/analyze`:**
```json
{
  "filename": "foto.jpg",
  "api_key": "AIza...",
  "prompt": "...",
  "max_size": 512,
  "gen_config": {
    "temperature": 0.1,
    "topP": 0.95,
    "maxOutputTokens": 512,
    "candidateCount": 1,
    "topK": 40,
    "stopSequences": ["FIN"]
  }
}
```

`max_size` acepta únicamente `512` o `768`. `gen_config` es opcional; si se omite se aplican los defaults del backend.

---

### Frontend (JavaScript incrustado en `server.py`)

La UI tiene dos pestañas:

**🔍 Individual** — analiza una sola imagen seleccionada del dataset. Muestra resultado en cards con tipo de envase, marca, estado y JSON raw.

**⚡ Batch** — procesa todas las imágenes secuencialmente con un delay configurable entre llamadas. Muestra progreso en tiempo real, grid con código de color por resultado, panel de detalle al hacer click, estadísticas globales y exportación a JSON.

**Estado global JS:**
```js
let selectedFile   // imagen seleccionada en vista individual
let allFiles       // lista de todas las imágenes del dataset
let batchResults   // { filename: { state, result, error } }
let batchRunning   // boolean — batch en curso
let batchAbort     // boolean — señal de parada
let currentRes     // resolución vista individual (512 | 768)
let batchRes       // resolución batch (512 | 768)
```

---

## Formato de respuesta del modelo

El modelo debe responder **únicamente** con un JSON válido siguiendo este esquema:

```json
{
  "objects": [
    {
      "type": "BOTTLE | CAN | ERROR",
      "name": "NOMBRE DE MARCA | ERROR",
      "status": "OK | NO OK",
      "description": "Descripción corta"
    }
  ]
}
```

Si no se detecta ninguna bebida, el modelo responde con `ERROR` (texto plano), que `parse_response` convierte al formato estándar con `type: ERROR`.

**Estados de resultado en batch:**
- `ok` — todos los objetos tienen `status: OK` y ninguno es ERROR
- `nok` — algún objeto tiene `status: NO OK` pero ninguno es ERROR
- `error` — algún objeto es ERROR, o la llamada a la API falló

---

## Modelo de IA

- **Modelo:** `gemma-3-27b-it`
- **API:** Google Generative Language v1beta
- **Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent`
- **Autenticación:** API Key de Google pasada como query param `?key=`

---

## Procesamiento de imágenes

Antes de enviar al modelo, cada imagen se:
1. Convierte a modo RGB (aplana transparencias sobre fondo blanco)
2. Redimensiona a máximo 512×512 o 768×768 px manteniendo la relación de aspecto (`Image.thumbnail`)
3. Comprime a JPEG con calidad 70
4. Codifica en base64 para incluirla en el payload de la API

---

## Consideraciones para modificaciones futuras

- **Añadir un nuevo campo al esquema JSON de respuesta** → modificar `DEFAULT_PROMPT` (la cadena del esquema) y la función `card()` en el JS para renderizarlo.
- **Cambiar el modelo** → modificar la URL en `call_gemma()`.
- **Añadir soporte a más formatos de imagen** → añadir extensión al set `IMAGE_EXTENSIONS`.
- **Cambiar el puerto** → modificar `app.run(port=5000)` al final del fichero.
- **Separar frontend del backend** → extraer la cadena `HTML` a un fichero `templates/index.html` y sustituir `render_template_string` por `render_template`.
- **El logo de i-mas** está incrustado como SVG tipográfico inline en el header. Para usar el logo oficial, sustituir el bloque `<svg>` por el contenido de `Logo.svg` de `https://i-mas.com/wp-content/uploads/Logo.svg`.

---

## Branding

Herramienta desarrollada internamente por **i-mas** (https://i-mas.com).
Paleta de colores: fondo `#0a0a0a`, acento `#c8f542`, tipografía Inter + DM Mono.
