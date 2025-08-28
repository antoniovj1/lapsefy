# app/core/deflicker.py
import cv2
import numpy as np
from .image_processor import ImageProcessor
from PySide6.QtCore import QObject, Signal


class Deflickerer(QObject):
    progress_updated = Signal(int)

    def __init__(self):
        super().__init__()
        self.processor = ImageProcessor()
        self.brightness_curve = []

    def calculate_brightness(self, image):
        """Calcula el brillo promedio de una imagen"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return np.mean(gray)

    def get_brightness_curve(self, image_sequence):
        """Calcula la curva de brillo para una secuencia de imágenes"""
        self.brightness_curve = []
        total = len(image_sequence)

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)
            if image is None:
                continue
            brightness = self.calculate_brightness(image)
            self.brightness_curve.append(brightness)

            progress = int(((i + 1) / total) * 100)
            self.progress_updated.emit(progress)

        return self.brightness_curve

    def get_smoothed_curve(self, window_size=10):
        """Suaviza la curva de brillo usando una media móvil"""
        if not self.brightness_curve:
            return []

        # Asegurar que el tamaño de la ventana sea impar para un centrado adecuado
        if window_size % 2 == 0:
            window_size += 1

        smoothed = np.convolve(self.brightness_curve, np.ones(window_size) / window_size, mode='same')

        # Corregir los bordes que la convolución no maneja bien
        half_window = window_size // 2
        for i in range(half_window):
            smoothed[i] = np.mean(self.brightness_curve[:i + half_window + 1])
            smoothed[-(i + 1)] = np.mean(self.brightness_curve[-(i + half_window + 1):])

        return smoothed.tolist()

    def apply_correction(self, image_sequence, smoothed_curve):
        """Aplica la corrección de brillo a la secuencia de imágenes"""
        processed_images = []
        total = len(image_sequence)

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)
            if image is None:
                continue

            # Calcular factor de corrección
            original_brightness = self.brightness_curve[i]
            target_brightness = smoothed_curve[i]

            if original_brightness > 0:
                correction_factor = target_brightness / original_brightness
            else:
                correction_factor = 1.0

            # Aplicar corrección
            corrected_image = image.astype(np.float32) * correction_factor
            corrected_image = np.clip(corrected_image, 0, 255).astype(np.uint8)

            processed_images.append(corrected_image)

            progress = int(((i + 1) / total) * 100)
            self.progress_updated.emit(progress)

        return processed_images
