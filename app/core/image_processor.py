# app/core/image_processor.py
import cv2
import numpy as np
import rawpy


class ImageProcessor:
    def __init__(self):
        self.preview_cache = {}
        self.MAX_CACHE_SIZE = 20

    def is_in_cache(self, image_path):
        """Comprueba si una imagen ya está en el caché."""
        return image_path in self.preview_cache

    def clear_cache(self):
        """Limpia el caché, útil al cargar una nueva secuencia."""
        self.preview_cache.clear()

    def load_image(self, image_path, use_cache=True):
        """Carga una imagen, soportando formatos RAW y JPEG, con opción de caché."""
        if use_cache and image_path in self.preview_cache:
            return self.preview_cache[image_path].copy()

        try:
            if image_path.lower().endswith(('.raw', '.cr2', '.nef', '.arw', '.raf')):
                with rawpy.imread(image_path) as raw:
                    # --- CAMBIO REALIZADO: Corrección de color avanzada ---
                    # Se aplica un espacio de color sRGB y una corrección gamma
                    # para obtener colores vibrantes y fieles a la cámara,
                    # similar a lo que hace el JPEG de la miniatura.
                    rgb = raw.postprocess(
                        use_camera_wb=True,
                        no_auto_bright=True,
                        output_color=rawpy.ColorSpace.sRGB,
                        gamma=(2.222, 4.5),
                        output_bps=8
                    )
                image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            else:
                image = cv2.imread(image_path)

            if use_cache and image is not None:
                if len(self.preview_cache) >= self.MAX_CACHE_SIZE:
                    self.preview_cache.pop(next(iter(self.preview_cache)))
                self.preview_cache[image_path] = image
                return image.copy()

            return image
        except Exception as e:
            print(f"Error al cargar la imagen {image_path}: {e}")
            return None

    def adjust_image_from_array(self, image, exposure=0, contrast=0):
        """Ajusta exposición y contraste de una imagen desde un array de numpy."""
        if image is None:
            return None

        result = image.copy().astype(np.float32)

        if exposure != 0:
            result = np.clip(result * (2.0 ** exposure), 0, 255)

        if contrast != 0:
            factor = (1.0 + contrast)
            mean = np.mean(result, axis=(0, 1), keepdims=True)
            result = np.clip((result - mean) * factor + mean, 0, 255)

        return result.astype(np.uint8)
