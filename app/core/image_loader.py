# app/core/image_loader.py
import os
import threading
from PySide6.QtCore import QObject, Signal
import cv2


class ImageLoader(QObject):
    progress_updated = Signal(int, str)  # progreso, mensaje
    finished = Signal(list)  # lista de rutas de imágenes

    def __init__(self):
        super().__init__()

    def load_images(self, folder):
        """Carga imágenes desde una carpeta en un hilo separado"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.raw', '.cr2', '.nef', '.arw', '.raf']
        image_files = []

        # Obtener lista de archivos
        try:
            files = os.listdir(folder)
            total_files = len(files)

            for i, file in enumerate(files):
                if any(file.lower().endswith(ext) for ext in supported_formats):
                    image_files.append(os.path.join(folder, file))

                # Emitir progreso
                progress = int(((i + 1) / total_files) * 50)  # La exploración es la primera mitad
                self.progress_updated.emit(progress, f"Explorando archivos: {i + 1}/{total_files}")

        except Exception as e:
            self.progress_updated.emit(0, f"Error al explorar carpeta: {str(e)}")
            self.finished.emit([])
            return

        # Ordenar archivos por nombre
        image_files.sort()

        # Emitir progreso final y lista de archivos
        self.progress_updated.emit(100, f"Carga completada: {len(image_files)} imágenes encontradas.")
        self.finished.emit(image_files)
