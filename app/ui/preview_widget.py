# app/ui/preview_widget.py (modificaciones)
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2
import numpy as np
import os


class PreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.current_pixmap = None

    def init_ui(self):
        # Layout principal
        layout = QVBoxLayout(self)

        # Información de la imagen
        self.info_layout = QHBoxLayout()
        self.filename_label = QLabel()
        self.filename_label.setAlignment(Qt.AlignLeft)
        self.resolution_label = QLabel()
        self.resolution_label.setAlignment(Qt.AlignRight)

        self.info_layout.addWidget(self.filename_label)
        self.info_layout.addWidget(self.resolution_label)
        layout.addLayout(self.info_layout)

        # Label para mostrar la imagen
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setText("Selecciona una carpeta con imágenes para comenzar")
        self.image_label.setWordWrap(True)

        # Configurar fuente más grande para el mensaje inicial
        font = QFont()
        font.setPointSize(14)
        self.image_label.setFont(font)

        layout.addWidget(self.image_label)

    def load_image(self, image_path):
        """Carga una imagen desde una ruta y la muestra"""
        try:
            # Actualizar información del archivo
            filename = os.path.basename(image_path)

            # Intentar cargar la imagen
            image = cv2.imread(image_path)
            if image is not None:
                # Actualizar información de resolución
                height, width = image.shape[:2]
                self.set_image(image, filename, width, height)
            else:
                self.image_label.setText(f"No se pudo cargar la imagen: {image_path}")
                # Restaurar fuente normal para mensajes de error
                font = QFont()
                font.setPointSize(10)
                self.image_label.setFont(font)
        except Exception as e:
            self.image_label.setText(f"Error al cargar imagen: {str(e)}")
            # Restaurar fuente normal para mensajes de error
            font = QFont()
            font.setPointSize(10)
            self.image_label.setFont(font)

    def set_image(self, image, filename="", width=0, height=0):
        """Muestra una imagen (array de numpy) en el widget"""
        try:
            # Actualizar información
            self.filename_label.setText(f"Archivo: {filename}")
            if width > 0 and height > 0:
                self.resolution_label.setText(f"Resolución: {width}x{height}")

            # Convertir BGR a RGB para mostrar correctamente
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image

            # Convertir a QImage
            h, w = image_rgb.shape[:2]

            if len(image_rgb.shape) == 3:
                bytes_per_line = 3 * w
                qt_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            else:
                bytes_per_line = w
                qt_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

            # Escalar la imagen para que se ajuste al label manteniendo la relación de aspecto
            pixmap = QPixmap.fromImage(qt_image)
            self.current_pixmap = pixmap

            scaled_pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.image_label.setPixmap(scaled_pixmap)
            # Restaurar fuente normal cuando se muestra una imagen
            font = QFont()
            font.setPointSize(10)
            self.image_label.setFont(font)

        except Exception as e:
            self.image_label.setText(f"Error al mostrar imagen: {str(e)}")
            # Restaurar fuente normal para mensajes de error
            font = QFont()
            font.setPointSize(10)
            self.image_label.setFont(font)

    def resizeEvent(self, event):
        """Maneja el redimensionamiento del widget"""
        super().resizeEvent(event)
        # Si hay una imagen cargada, reescalarla al nuevo tamaño
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)