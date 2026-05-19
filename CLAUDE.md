# NIVHIS Prompt Trainer — CLAUDE.md

Herramienta interna de i-mas para evaluar y afinar prompts de visión artificial sobre un dataset de imágenes de bebidas. Soporta múltiples proveedores de IA (Google AI, Groq, OpenRouter) y permite análisis individual o en batch.

---

## Estructura del proyecto

```
./
├── server.py          # Servidor Flask + toda la UI (HTML/CSS/JS incrustados)
├── requirements.txt   # Dependencias Python
├── README.md          # Guía de uso y arranque para usuarios
├── CLAUDE.md          # Este fichero — documentación técnica
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
- `MAX_SIZE = (512, 512)` — resolución de compresión por defecto (fallback)
- `JPEG_QUALITY = 70` — calidad JPEG de compresión
- `DEFAULT_PROMPT` — prompt base en español para identificación de bebidas

**Funciones principales:**

| Función | Descripción |
|---|---|
| `compress_image(path, max_size)` | Convierte cualquier imagen a JPEG, redimensiona a `max_size` manteniendo aspect ratio, aplica calidad 70 |
| `call_api(provider, api_key, jpeg_bytes, media_type, prompt, generation_config, model)` | Llama al proveedor seleccionado y devuelve siempre una respuesta en formato Google (normalizado) |
| `parse_response(api_resp)` | Extrae el texto ignorando las `parts` con `"thought": true`, busca el JSON entre etiquetas `<result>` y lo parsea |

**Rutas Flask:**

| Ruta | Método | Descripción |
|---|---|---|
| `/` | GET | Sirve el HTML de la aplicación |
| `/api/files` | GET | Lista las imágenes en `./dataset` |
| `/api/image/<filename>` | GET | Sirve la imagen original |
| `/api/thumbnail/<filename>` | GET | Sirve una miniatura 120×120px |
| `/api/models?key=&provider=` | GET | Lista los modelos disponibles para el proveedor y API Key dados |
| `/api/analyze` | POST | Analiza una imagen con el proveedor/modelo seleccionado |

**Payload de `/api/analyze`:**
```json
{
  "filename": "foto.jpg",
  "api_key": "...",
  "prompt": "...",
  "max_size": 512,
  "model": "gemma-4-31b-it",
  "provider": "google",
  "gen_config": {
    "temperature": 0.1,
    "topP": 0.95,
    "maxOutputTokens": 1024,
    "topK": 40,
    "stopSequences": ["FIN"]
  }
}
```

- `max_size` acepta `512` o `768`.
- `provider` acepta `"google"`, `"groq"` o `"openrouter"`.
- `gen_config` es opcional; si se omite se usan los defaults del backend.
- `candidateCount` fue eliminado — no está soportado por los modelos actuales y causaba errores 500.

---

### Proveedores de IA soportados

| Proveedor | Formato API | Dónde obtener la key | Modelo por defecto UI |
|---|---|---|---|
| `google` | Google Generative Language v1beta | [aistudio.google.com](https://aistudio.google.com/app/apikey) | `gemma-4-31b-it` |
| `groq` | OpenAI-compatible | [console.groq.com](https://console.groq.com/keys) | `meta-llama/llama-4-scout-17b-16e-instruct` |
| `openrouter` | OpenAI-compatible | [openrouter.ai/keys](https://openrouter.ai/keys) | `qwen/qwen2.5-vl-72b-instruct:free` |

`call_api` normaliza la respuesta de Groq y OpenRouter (formato OpenAI) al formato Google internamente, de modo que `parse_response` funciona igual para los tres proveedores.

---

### Extracción del JSON de respuesta

Algunos modelos incluyen razonamiento interno antes de la respuesta. El parser aplica la siguiente estrategia en cascada:

1. **Filtra `parts` con `"thought": true`** — ignora el razonamiento interno que devuelve Google en una part separada.
2. **Busca `<result>...</result>`** — el prompt pide al modelo que envuelva el JSON entre estas etiquetas.
3. **Busca bloque ` ```json ``` `** — fallback si el modelo usa markdown.
4. **Extrae por primera `{` / última `}`** — último recurso posicional.
5. **Texto plano `ERROR`** — si no hay bebida, convierte a objeto de error estándar.

---

### Frontend (JavaScript incrustado en `server.py`)

La UI tiene dos pestañas:

**🔍 Individual** — analiza una sola imagen seleccionada del dataset. Muestra resultado en cards con tipo de envase, marca, estado y JSON raw.

**⚡ Batch** — procesa todas las imágenes secuencialmente con un delay configurable. Muestra progreso en tiempo real, grid con código de color, panel de detalle al hacer click, estadísticas globales y exportación a JSON.

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

**Funciones JS clave:**

| Función | Descripción |
|---|---|
| `callAnalyze(filename, key, prompt, maxSize, genConfig)` | Llama a `/api/analyze` con proveedor y modelo del selector del header |
| `listModels()` | Llama a `/api/models` y puebla el `<select>` de modelos |
| `onProviderChange()` | Al cambiar proveedor, actualiza placeholder del API Key y modelo por defecto |
| `getGenConfig(prefix)` | Lee los campos de Generation Config del panel y devuelve el objeto |
| `startBatch()` / `stopBatch()` | Inicia/detiene el procesamiento en batch |
| `showDetail(filename)` | Muestra el resultado detallado de una imagen en el panel derecho del batch |
| `exportResults()` | Descarga todos los resultados del batch como JSON |

---

## Formato de respuesta del modelo

El prompt instruye al modelo a devolver **únicamente** JSON envuelto en `<result>...</result>`:

```json
{
  "objects": [
    {
      "type": "BOTTLE | CAN | ERROR",
      "name": "BRAND NAME | ERROR",
      "status": "OK | NO OK",
      "description": "Descripción corta con datos curiosos sobre la bebida y la temperatura ideal de consumición"
    }
  ]
}
```

- `name: ERROR` cuando no se puede identificar la marca con certeza (sin nombre visible ni logo).
- No se admite un nombre incorrecto — es preferible ERROR ante cualquier duda.
- Si hay varias bebidas parecidas, no se asume la marca de ninguna sin certeza.
- Si no hay ninguna bebida, el modelo responde `ERROR` (texto plano).

**Estados de resultado en batch:**
- `ok` — todos los objetos tienen `status: OK` y ninguno es ERROR
- `nok` — algún objeto tiene `status: NO OK` pero ninguno es ERROR
- `error` — algún objeto es ERROR, o la llamada a la API falló

---

## Procesamiento de imágenes

Antes de enviar al modelo, cada imagen se:
1. Convierte a modo RGB (aplana transparencias sobre fondo blanco)
2. Redimensiona a máximo 512×512 o 768×768 px manteniendo la relación de aspecto (`Image.thumbnail`)
3. Comprime a JPEG con calidad 70
4. Codifica en base64 para incluirla en el payload de la API

---

## Consideraciones para modificaciones futuras

- **Añadir un campo al esquema JSON** → modificar `DEFAULT_PROMPT` y la función `card()` en el JS.
- **Añadir un nuevo proveedor** → añadir rama en `call_api()`, en `list_models()`, en `PROVIDER_DEFAULTS` del JS y en el `<select id="providerSelect">` del HTML.
- **Cambiar el puerto** → modificar `app.run(port=5000)` al final del fichero.
- **Separar frontend del backend** → extraer la cadena `HTML` a `templates/index.html` y sustituir `render_template_string` por `render_template`.
- **Añadir soporte a más formatos de imagen** → añadir extensión al set `IMAGE_EXTENSIONS`.
- **El logo de i-mas** está incrustado como SVG tipográfico inline en el header. Para usar el logo oficial, sustituir el bloque `<svg>` por el contenido de `Logo.svg` de `https://i-mas.com/wp-content/uploads/Logo.svg`.

---

## Branding

Herramienta desarrollada internamente por **i-mas** ([i-mas.com](https://i-mas.com)).
Paleta de colores: fondo `#0a0a0a`, acento `#c8f542`, tipografía Inter + DM Mono.
