# app/ui/preview_widget.py
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStackedLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2
import numpy as np
import os


class PreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_pixmap = None
        self.loading_animation_timer = QTimer(self)
        self.loading_animation_timer.setInterval(300)
        self.loading_animation_timer.timeout.connect(self.animate_loading_text)
        self.dot_count = 0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        self.info_layout = QHBoxLayout()
        self.filename_label = QLabel("Archivo: Ninguno")
        self.resolution_label = QLabel("Resolución: -")
        self.info_layout.addWidget(self.filename_label)
        self.info_layout.addWidget(self.resolution_label)
        main_layout.addLayout(self.info_layout)

        self.stacked_layout = QStackedLayout()

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setFrameStyle(QLabel.NoFrame)
        # --- CAMBIO REALIZADO: Fondo transparente ---
        # Esto asegura que no se muestre ningún color de fondo alrededor
        # de la imagen, eliminando la línea lateral.
        self.image_label.setStyleSheet("background-color: transparent;")

        self.loading_label = QLabel()
        self.loading_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        self.loading_label.setFont(font)

        self.stacked_layout.addWidget(self.image_label)
        self.stacked_layout.addWidget(self.loading_label)

        main_layout.addLayout(self.stacked_layout, 1)

    def show_loading(self):
        self.dot_count = 0
        self.loading_label.setText("Cargando")
        self.stacked_layout.setCurrentWidget(self.loading_label)
        self.loading_animation_timer.start()

    def animate_loading_text(self):
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.loading_label.setText(f"Cargando{dots}")

    def set_image(self, image, filename="", width=0, height=0):
        self.loading_animation_timer.stop()
        self.image_label.clear()
        try:
            self.filename_label.setText(f"Archivo: {filename}")
            if width > 0 and height > 0:
                self.resolution_label.setText(f"Resolución: {width}x{height}")

            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w, ch = image_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            else:
                image_rgb = image
                h, w = image_rgb.shape
                bytes_per_line = w
                qt_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

            self.current_pixmap = QPixmap.fromImage(qt_image)
            self.update_pixmap_scaling()

        except Exception as e:
            self.current_pixmap = None
            self.image_label.setText(f"Error al mostrar imagen:\n{str(e)}")

        self.stacked_layout.setCurrentWidget(self.image_label)

    def update_pixmap_scaling(self):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap_scaling()
