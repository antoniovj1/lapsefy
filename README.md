# Timelapse Creator

Una aplicación de escritorio para crear timelapses a partir de secuencias de imágenes RAW o JPEG.

## Características

- Importar secuencias de imágenes (RAW, JPEG, PNG, etc.)
- Previsualización de imágenes
- Ajustes básicos: exposición y contraste
- Deflickering para suavizar variaciones de brillo
- Exportación a varios formatos de video (MP4, MOV, AVI)
- Soporte para múltiples codecs (H.264, H.265, MPEG-4, ProRes)
- Interfaz gráfica intuitiva

## Requisitos

- Python 3.7+
- FFmpeg instalado en el sistema

## Instalación

1. Clona o descarga el proyecto
2. Crea un entorno virtual: `python -m venv venv`
3. Activa el entorno virtual:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Instala las dependencias: `pip install -r requirements.txt`

## Uso

1. Ejecuta la aplicación: `python -m app.main`
2. Haz clic en "Seleccionar carpeta de imágenes" para importar una secuencia
3. Ajusta la exposición y contraste si es necesario
4. Aplica deflickering para suavizar variaciones de brillo
5. Configura los parámetros de exportación (FPS, resolución, codec)
6. Haz clic en "Exportar Timelapse" para guardar el video

## Solución de problemas

### Error "FFmpeg no encontrado"
Asegúrate de tener FFmpeg instalado y disponible en el PATH del sistema.

### Las imágenes RAW no se cargan
Instala las dependencias necesarias: `pip install rawpy`

### La aplicación se cierra inesperadamente
Verifica que todas las dependencias estén instaladas correctamente.