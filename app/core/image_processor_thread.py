# app/core/image_processor_thread.py
from PySide6.QtCore import QThread, Signal
from app.core.image_processor import ImageProcessor

class ImageProcessorThread(QThread):
    processing_done = Signal(object)  # Emite la imagen procesada
    processing_error = Signal(str)    # Emite mensajes de error

    def __init__(self):
        super().__init__()
        self.processor = ImageProcessor()
        self.image_path = None
        self.exposure = 0
        self.contrast = 0
        self.current_request_id = 0

    def set_parameters(self, image_path, exposure, contrast, request_id):
        self.image_path = image_path
        self.exposure = exposure
        self.contrast = contrast
        self.current_request_id = request_id

    def run(self):
        if self.image_path:
            try:
                # Procesar la imagen con los parámetros actuales
                processed_image = self.processor.adjust_image(
                    self.image_path,
                    self.exposure,
                    self.contrast
                )
                # Incluir el ID de la solicitud en el resultado
                self.processing_done.emit((processed_image, self.current_request_id))
            except Exception as e:
                self.processing_error.emit(f"Error al procesar imagen: {str(e)}")