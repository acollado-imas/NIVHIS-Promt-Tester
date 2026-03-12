# NIVHIS Prompt Trainer

Herramienta interna de **i-mas** para evaluar y afinar prompts de visión artificial sobre datasets de imágenes de bebidas. Permite analizar imágenes individualmente o en batch usando el modelo **Gemma 3 27B** de Google, y comparar cómo distintos prompts afectan a la calidad de los resultados.

---

## ¿Qué hace?

- **Carga un dataset de imágenes** desde la carpeta `./dataset` y las muestra con miniatura.
- **Analiza imágenes individualmente** — selecciona una imagen, edita el prompt y lanza el análisis. El resultado se muestra en cards con tipo de envase (botella/lata), marca detectada, estado (OK / NO OK) y descripción.
- **Analiza en batch** — procesa todas las imágenes del dataset de forma secuencial con el mismo prompt. Muestra progreso en tiempo real, código de color por resultado y estadísticas globales.
- **Ajusta los parámetros del modelo** — temperatura, Top P, Top K, Max Tokens, Candidate Count y Stop Sequences, configurables desde la propia interfaz.
- **Exporta los resultados** del batch a un fichero JSON descargable.

---

## Requisitos previos

- **Python 3.10 o superior**
- **Una API Key de Google Generative Language** con acceso al modelo `gemma-3-27b-it`
  → Puedes obtenerla en [Google AI Studio](https://aistudio.google.com/app/apikey)

---

## Instalación y ejecución

### 🪟 Windows

1. Abre **PowerShell** o el **Símbolo del sistema (cmd)**.

2. Comprueba que tienes Python instalado:
   ```powershell
   python --version
   ```
   Si no lo tienes, descárgalo desde [python.org](https://www.python.org/downloads/) y marca la opción **"Add Python to PATH"** durante la instalación.

3. Navega a la carpeta del proyecto:
   ```powershell
   cd C:\ruta\al\proyecto
   ```

4. Crea un entorno virtual e instala las dependencias:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. Crea la carpeta `dataset` y añade tus imágenes:
   ```powershell
   mkdir dataset
   # Copia aquí tus imágenes (.jpg, .png, .webp, etc.)
   ```

6. Arranca el servidor:
   ```powershell
   python server.py
   ```

7. Abre tu navegador en **http://localhost:5000**

---

### 🍎 macOS

1. Abre **Terminal**.

2. Comprueba que tienes Python instalado:
   ```bash
   python3 --version
   ```
   Si no lo tienes, instálalo con [Homebrew](https://brew.sh):
   ```bash
   brew install python
   ```

3. Navega a la carpeta del proyecto:
   ```bash
   cd /ruta/al/proyecto
   ```

4. Crea un entorno virtual e instala las dependencias:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Crea la carpeta `dataset` y añade tus imágenes:
   ```bash
   mkdir dataset
   # Copia aquí tus imágenes (.jpg, .png, .webp, etc.)
   ```

6. Arranca el servidor:
   ```bash
   python server.py
   ```

7. Abre tu navegador en **http://localhost:5000**

---

### 🐧 Linux (Ubuntu)

1. Abre una **terminal**.

2. Comprueba que tienes Python instalado:
   ```bash
   python3 --version
   ```
   Si no lo tienes:
   ```bash
   sudo apt update && sudo apt install python3 python3-pip python3-venv
   ```

3. Navega a la carpeta del proyecto:
   ```bash
   cd /ruta/al/proyecto
   ```

4. Crea un entorno virtual e instala las dependencias:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Crea la carpeta `dataset` y añade tus imágenes:
   ```bash
   mkdir dataset
   # Copia aquí tus imágenes (.jpg, .png, .webp, etc.)
   ```

6. Arranca el servidor:
   ```bash
   python server.py
   ```

7. Abre tu navegador en **http://localhost:5000**

---

## Uso básico

### 1. Introduce tu API Key
En la esquina superior derecha encontrarás el campo **API Key**. Introduce tu clave de Google Generative Language. Se mantiene en memoria mientras la sesión esté activa.

### 2. Análisis individual
- Ve a la pestaña **🔍 Individual**.
- Haz click en cualquier imagen del panel izquierdo para previsualizarla.
- Edita el prompt si lo deseas (o déjalo por defecto).
- Pulsa **Analizar**. El resultado aparece en el panel derecho.

### 3. Análisis en batch
- Ve a la pestaña **⚡ Batch**.
- Edita el prompt si lo deseas.
- Ajusta el **delay** entre llamadas (en segundos) para no saturar la API.
- Pulsa **▶ Iniciar Batch**. Las imágenes se procesarán una a una mostrando el progreso.
- Haz click en cualquier imagen del grid para ver su resultado detallado.
- Al finalizar, pulsa **⬇ Exportar JSON** para descargar todos los resultados.

### 4. Ajustar parámetros del modelo
Tanto en la vista individual como en el batch, despliega la sección **⚙ Generation Config** para ajustar temperatura, Top P, Top K, número máximo de tokens, etc.

### 5. Añadir nuevas imágenes
Copia las imágenes en la carpeta `./dataset` y pulsa el botón **↺** en el panel del dataset para recargar la lista sin reiniciar el servidor.

---

## Formatos de imagen soportados

`.jpg` · `.jpeg` · `.png` · `.webp` · `.bmp` · `.gif` · `.tiff`

---

## Formato de resultados

Cada análisis devuelve un JSON con la siguiente estructura:

```json
{
  "objects": [
    {
      "type": "BOTTLE | CAN | ERROR",
      "name": "Nombre de la marca detectada",
      "status": "OK | NO OK",
      "description": "Descripción corta con datos curiosos sobre la bebida y la temperatura ideal de consumición"
    }
  ]
}
```

El modelo responde `name: ERROR` cuando no puede identificar la marca con suficiente certeza (no encuentra el nombre, el logo o parte de ellos). Si hay varias bebidas parecidas en la misma imagen, no asume la marca de ninguna si no está seguro.

---

## Estructura de carpetas

```
./
├── server.py          # Servidor Flask + interfaz web
├── requirements.txt   # Dependencias Python
├── README.md          # Este fichero
├── CLAUDE.md          # Documentación técnica para desarrollo con IA
└── dataset/           # Carpeta con las imágenes del dataset
```

---

## Solución de problemas frecuentes

**El servidor no arranca**
Comprueba que el entorno virtual está activado y que las dependencias están instaladas: `pip install -r requirements.txt`.

**No aparecen imágenes en el panel**
Verifica que la carpeta `./dataset` existe y contiene imágenes en un formato soportado. Pulsa ↺ para recargar.

**Error 400 / API Key inválida**
Comprueba que la API Key es correcta y que tiene acceso habilitado para el modelo `gemma-3-27b-it` en Google AI Studio.

**Error 502 / tiempo de espera agotado**
La API de Google puede estar sobrecargada o el modelo tardando más de lo esperado. Aumenta el delay en el batch y vuelve a intentarlo.

**Respuesta no parseable**
Ocurre cuando el modelo no respeta el formato JSON solicitado. Prueba a bajar la temperatura (0.0–0.2) en Generation Config para hacer la respuesta más determinista.

---

*Desarrollado por i-mas — [i-mas.com](https://i-mas.com)*
