# app/core/deflicker.py
import cv2
import numpy as np
from .image_processor import ImageProcessor
from PySide6.QtCore import QObject, Signal


class Deflickerer(QObject):
    progress_updated = Signal(int)

    def __init__(self, window_size=10):
        super().__init__()
        self.window_size = window_size
        self.processor = ImageProcessor()

    def calculate_brightness(self, image):
        """Calcula el brillo promedio de una imagen"""
        if len(image.shape) == 3:
            # Convertir a escala de grises si es color
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return np.mean(gray)

    def get_brightness_curve(self, image_sequence):
        """Calcula la curva de brillo para una secuencia de imágenes"""
        brightness_values = []
        total = len(image_sequence)

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)
            brightness = self.calculate_brightness(image)
            brightness_values.append(brightness)

            # Emitir progreso (25% del proceso total es calcular el brillo)
            progress = int((i / total) * 25)
            self.progress_updated.emit(progress)

        return brightness_values

    def smooth_curve(self, values):
        """Suaviza una curva usando media móvil"""
        smoothed = []
        for i in range(len(values)):
            start = max(0, i - self.window_size // 2)
            end = min(len(values), i + self.window_size // 2 + 1)
            window = values[start:end]
            smoothed.append(sum(window) / len(window))
        return smoothed

    def process_sequence(self, image_sequence):
        """Aplica deflickering a una secuencia de imágenes"""
        # Calcular curva de brillo original
        brightness_curve = self.get_brightness_curve(image_sequence)

        # Suavizar la curva
        smoothed_curve = self.smooth_curve(brightness_curve)

        # Procesar cada imagen
        processed_images = []
        total = len(image_sequence)

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)

            # Calcular factor de corrección
            if brightness_curve[i] > 0:
                correction_factor = smoothed_curve[i] / brightness_curve[i]
            else:
                correction_factor = 1.0

            # Aplicar corrección
            corrected_image = image.astype(np.float32) * correction_factor
            corrected_image = np.clip(corrected_image, 0, 255).astype(np.uint8)

            processed_images.append(corrected_image)

            # Emitir progreso (25-100% del proceso total es aplicar corrección)
            progress = 25 + int((i / total) * 75)
            self.progress_updated.emit(progress)

        return processed_images