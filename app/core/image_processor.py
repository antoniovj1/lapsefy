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
                    # --- CAMBIO REALIZADO: Consistencia de color ---
                    # Usar los mismos parámetros que en las miniaturas para colores fieles.
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
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

    def adjust_image(self, image_path, exposure=0, contrast=0):
        """Ajusta exposición y contraste de una imagen."""
        # Al ajustar, no usamos el caché para obtener la imagen original
        image = self.load_image(image_path, use_cache=False)
        return self.adjust_image_from_array(image, exposure, contrast)

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

    def process_sequence(self, image_paths, exposure=0, contrast=0):
        """Procesa una secuencia completa de imágenes con los ajustes dados"""
        processed_images = []
        for image_path in image_paths:
            original_image = self.load_image(image_path, use_cache=True)
            processed_image = self.adjust_image_from_array(original_image, exposure, contrast)
            if processed_image is not None:
                processed_images.append(processed_image)
        return processed_images
