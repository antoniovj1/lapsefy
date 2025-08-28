# app/core/image_processor.py
import cv2
import numpy as np
import rawpy


class ImageProcessor:
    def __init__(self):
        # Cache para imágenes RAW procesadas
        self.raw_cache = {}

    def load_image(self, image_path):
        """Carga una imagen, soportando formatos RAW y JPEG"""
        if image_path.lower().endswith(('.raw', '.cr2', '.nef', '.arw')):
            # Usar cache para imágenes RAW (son lentas de procesar)
            if image_path in self.raw_cache:
                return self.raw_cache[image_path].copy()

            # Procesar imagen RAW
            with rawpy.imread(image_path) as raw:
                rgb = raw.postprocess()
            result = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            # Almacenar en cache (limitar el tamaño del cache)
            if len(self.raw_cache) > 10:
                self.raw_cache.clear()
            self.raw_cache[image_path] = result

            return result
        else:
            # Cargar imagen normal
            return cv2.imread(image_path)

    def adjust_image(self, image_path, exposure=0, contrast=0):
        """Ajusta exposición y contraste de una imagen"""
        image = self.load_image(image_path)
        return self.adjust_image_from_array(image, exposure, contrast)

    def adjust_image_from_array(self, image, exposure=0, contrast=0):
        """Ajusta exposición y contraste de una imagen desde un array"""
        if image is None:
            return None

        # Hacer una copia para no modificar la original
        result = image.copy().astype(np.float32)

        # Aplicar exposición (forma más eficiente)
        if exposure != 0:
            # exposure está en el rango [-1, 1] después de dividir por 100
            result = result * (2.0 ** exposure)

        # Aplicar contraste (forma más eficiente)
        if contrast != 0:
            # contrast está en el rango [-1, 1] después de dividir por 100
            mean = np.mean(result, axis=(0, 1))
            result = (result - mean) * (1.0 + contrast) + mean

        # Asegurar que los valores estén en el rango correcto
        result = np.clip(result, 0, 255).astype(np.uint8)

        return result

    def process_sequence(self, image_paths, exposure=0, contrast=0):
        """Procesa una secuencia completa de imágenes con los ajustes dados"""
        processed_images = []
        for image_path in image_paths:
            processed_image = self.adjust_image(image_path, exposure, contrast)
            if processed_image is not None:
                processed_images.append(processed_image)
        return processed_images