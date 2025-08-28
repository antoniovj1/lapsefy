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
        supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.raw', '.cr2', '.nef', '.arw']
        image_files = []

        # Obtener lista de archivos
        try:
            files = os.listdir(folder)
            total_files = len(files)

            for i, file in enumerate(files):
                if any(file.lower().endswith(ext) for ext in supported_formats):
                    image_files.append(os.path.join(folder, file))

                # Emitir progreso
                progress = int((i / total_files) * 100)
                self.progress_updated.emit(progress, f"Explorando archivos: {i}/{total_files}")

        except Exception as e:
            self.progress_updated.emit(0, f"Error al explorar carpeta: {str(e)}")
            self.finished.emit([])
            return

        # Ordenar archivos
        image_files.sort()

        # Verificar que las imágenes se pueden cargar
        valid_images = []
        total_images = len(image_files)

        for i, image_path in enumerate(image_files):
            try:
                # Intentar cargar la imagen para verificar que es válida
                img = cv2.imread(image_path)
                if img is not None:
                    valid_images.append(image_path)

                # Emitir progreso
                progress = int((i / total_images) * 100)
                self.progress_updated.emit(progress, f"Verificando imágenes: {i}/{total_images}")

            except Exception as e:
                print(f"Error al verificar imagen {image_path}: {e}")

        self.progress_updated.emit(100, f"Carga completada: {len(valid_images)} imágenes")
        self.finished.emit(valid_images)