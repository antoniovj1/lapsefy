# app/core/deflicker.py
import cv2
import numpy as np
from .image_processor import ImageProcessor
from PySide6.QtCore import QObject, Signal
from scipy import signal
import threading
import time


class Deflickerer(QObject):
    progress_updated = Signal(int)
    preview_ready = Signal(int, np.ndarray)  # frame_index, processed_image

    def __init__(self):
        super().__init__()
        self.processor = ImageProcessor()
        self.brightness_curve = []
        self.smoothing_method = "moving_average"
        self.smoothing_params = {}

    def calculate_brightness(self, image):
        """Calcula el brillo promedio de una imagen usando diferentes métodos"""
        if len(image.shape) == 3:
            # Convertir a espacio de color LAB y usar el canal L (luminancia)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            return np.mean(l_channel)
        else:
            return np.mean(image)

    def get_brightness_curve(self, image_sequence):
        """Calcula la curva de brillo para una secuencia de imágenes"""
        self.brightness_curve = []
        total = len(image_sequence)

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)
            if image is None:
                # Si no podemos cargar la imagen, usar el valor anterior o 0
                brightness = self.brightness_curve[-1] if self.brightness_curve else 0
                self.brightness_curve.append(brightness)
                continue

            brightness = self.calculate_brightness(image)
            self.brightness_curve.append(brightness)

            progress = int(((i + 1) / total) * 100)
            self.progress_updated.emit(progress)

        return self.brightness_curve

    def set_smoothing_method(self, method, params=None):
        """Establecer el método de suavizado y sus parámetros"""
        self.smoothing_method = method
        self.smoothing_params = params or {}

    def get_smoothed_curve(self, smoothing_level, method=None, params=None):
        """Suaviza la curva de brillo usando el método seleccionado"""
        if not self.brightness_curve:
            return []

        # Usar método y parámetros proporcionados o los predeterminados
        method = method or self.smoothing_method
        params = params or self.smoothing_params

        # Convertir a array numpy
        curve = np.array(self.brightness_curve)

        # Calcular parámetros de suavizado basados en el nivel y la longitud de la curva
        window_size = params.get('window_size', max(3, min(101, int(len(curve) * smoothing_level / 200))))
        if window_size % 2 == 0:
            window_size += 1

        sigma = params.get('sigma', max(1, smoothing_level / 20))
        order = params.get('order', 3)

        if method == "moving_average":
            smoothed = self.moving_average_smooth(curve, window_size)
        elif method == "gaussian":
            smoothed = self.gaussian_smooth(curve, window_size, sigma)
        elif method == "savitzky_golay":
            smoothed = self.savitzky_golay_smooth(curve, window_size, order)
        elif method == "wavelet":
            smoothed = self.wavelet_smooth(curve, sigma)
        elif method == "loess":
            smoothed = self.loess_smooth(curve, window_size)
        else:
            smoothed = curve

        return smoothed.tolist()

    def moving_average_smooth(self, data, window_size):
        """Suavizado por media móvil con manejo de bordes"""
        half_window = window_size // 2
        smoothed = np.zeros_like(data, dtype=np.float64)

        for i in range(len(data)):
            start = max(0, i - half_window)
            end = min(len(data), i + half_window + 1)
            smoothed[i] = np.mean(data[start:end])

        return smoothed

    def gaussian_smooth(self, data, window_size, sigma):
        """Suavizado con filtro gaussiano"""
        # Crear kernel gaussiano
        x = np.arange(-window_size // 2, window_size // 2 + 1)
        kernel = np.exp(-x ** 2 / (2 * sigma ** 2))
        kernel /= np.sum(kernel)

        # Aplicar convolución
        smoothed = np.convolve(data, kernel, mode='same')
        return smoothed

    def savitzky_golay_smooth(self, data, window_size, order):
        """Suavizado con filtro Savitzky-Golay (preserva mejor los picos)"""
        if len(data) < window_size:
            return data

        return signal.savgol_filter(data, window_size, order)

    def wavelet_smooth(self, data, sigma):
        """Suavizado usando transformada wavelet"""
        if not HAS_PYWT:
            print("Advertencia: pywt no instalado. Usando media móvil como alternativa.")
            return self.moving_average_smooth(data, 21)

        try:
            import pywt
            # Descomposición wavelet
            coeffs = pywt.wavedec(data, 'db4', level=4)
            # Umbralizado de coeficientes
            coeffs[1:] = [pywt.threshold(c, sigma * np.std(c), 'soft') for c in coeffs[1:]]
            # Reconstrucción
            smoothed = pywt.waverec(coeffs, 'db4')
            # Ajustar longitud si es necesario
            if len(smoothed) > len(data):
                smoothed = smoothed[:len(data)]
            elif len(smoothed) < len(data):
                smoothed = np.pad(smoothed, (0, len(data) - len(smoothed)), 'edge')

            return smoothed
        except Exception as e:
            print(f"Error en suavizado wavelet: {e}")
            return self.moving_average_smooth(data, 21)

    def loess_smooth(self, data, window_size):
        """Suavizado LOESS (regresión local)"""
        if not HAS_STATSMODELS:
            print("Advertencia: statsmodels no instalado. Usando media móvil como alternativa.")
            return self.moving_average_smooth(data, window_size)

        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            x = np.arange(len(data))
            frac = window_size / len(data)
            smoothed = lowess(data, x, frac=frac, it=0, return_sorted=False)
            return smoothed
        except Exception as e:
            print(f"Error en suavizado LOESS: {e}")
            return self.moving_average_smooth(data, window_size)

    def generate_preview(self, frame_index, image_sequence, smoothed_curve):
        """Generar una previsualización del frame con la corrección aplicada"""
        if (not image_sequence or frame_index >= len(image_sequence) or
                not smoothed_curve or frame_index >= len(smoothed_curve)):
            print(f"Parámetros inválidos para generar previsualización")
            return None

        image_path = image_sequence[frame_index]
        image = self.processor.load_image(image_path)
        if image is None:
            print(f"No se pudo cargar la imagen: {image_path}")
            return None

        # Calcular factor de corrección
        original_brightness = self.brightness_curve[frame_index]
        target_brightness = smoothed_curve[frame_index]

        if original_brightness > 0:
            correction_factor = target_brightness / original_brightness
        else:
            correction_factor = 1.0

        print(f"Corrección aplicada: factor {correction_factor:.2f}")

        # Aplicar corrección en espacio LAB para mejor preservación del color
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = np.clip(lab[:, :, 0].astype(np.float32) * correction_factor, 0, 255).astype(np.uint8)
            corrected_image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            corrected_image = np.clip(image.astype(np.float32) * correction_factor, 0, 255).astype(np.uint8)

        return corrected_image

    def apply_correction(self, image_sequence, smoothed_curve):
        """Aplica la corrección de brillo a la secuencia de imágenes"""
        processed_images = []
        total = len(image_sequence)

        if len(smoothed_curve) != total:
            raise ValueError("La curva suavizada debe tener la misma longitud que la secuencia de imágenes")

        for i, image_path in enumerate(image_sequence):
            image = self.processor.load_image(image_path)
            if image is None:
                processed_images.append(None)
                continue

            # Calcular factor de corrección
            original_brightness = self.brightness_curve[i]
            target_brightness = smoothed_curve[i]

            if original_brightness > 0:
                correction_factor = target_brightness / original_brightness
            else:
                correction_factor = 1.0

            # Aplicar corrección en espacio LAB para mejor preservación del color
            if len(image.shape) == 3:
                lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
                lab[:, :, 0] = np.clip(lab[:, :, 0].astype(np.float32) * correction_factor, 0, 255).astype(np.uint8)
                corrected_image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                corrected_image = np.clip(image.astype(np.float32) * correction_factor, 0, 255).astype(np.uint8)

            processed_images.append(corrected_image)

            progress = int(((i + 1) / total) * 100)
            self.progress_updated.emit(progress)

        return processed_images