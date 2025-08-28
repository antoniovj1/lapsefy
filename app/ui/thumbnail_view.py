# app/ui/thumbnail_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                               QGridLayout, QSizePolicy, QPushButton)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QImage, QIcon
import cv2
import numpy as np
import threading
from PySide6.QtCore import QObject


class ThumbnailLoader(QObject):
    progress = Signal(int, QPixmap, str)  # índice, miniatura, ruta
    finished = Signal()

    def __init__(self, image_paths, thumbnail_size=100):
        super().__init__()
        self.image_paths = image_paths
        self.thumbnail_size = thumbnail_size
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        """Carga miniaturas en un hilo separado"""
        for i, image_path in enumerate(self.image_paths):
            if self._is_cancelled:
                break

            try:
                # Cargar imagen
                image = cv2.imread(image_path)
                if image is not None:
                    # Crear miniatura
                    thumbnail = self.create_thumbnail(image)
                    self.progress.emit(i, thumbnail, image_path)
            except Exception as e:
                print(f"Error al cargar miniatura {image_path}: {e}")

        self.finished.emit()

    def create_thumbnail(self, image):
        """Crea una miniatura a partir de una imagen"""
        # Redimensionar imagen para miniatura
        height, width = image.shape[:2]
        max_size = self.thumbnail_size

        # Calcular nuevas dimensiones manteniendo la relación de aspecto
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        # Redimensionar
        resized = cv2.resize(image, (new_width, new_height))

        # Convertir a QImage
        if len(resized.shape) == 3:
            rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        else:
            h, w = resized.shape
            bytes_per_line = w
            qt_image = QImage(resized.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

        return QPixmap.fromImage(qt_image)


class ThumbnailView(QWidget):
    # Señal personalizada que se emitirá cuando se haga clic en una miniatura
    thumbnail_clicked = Signal(str)  # Emite la ruta de la imagen

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thumbnails = []
        self.thumbnail_loader = None
        self.selected_thumbnail = None

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Título
        self.title_label = QLabel("Miniaturas de imágenes (haz clic para ver en grande)")
        layout.addWidget(self.title_label)

        # Área de scroll para las miniaturas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Widget contenedor para la cuadrícula de miniaturas
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

        # Información
        self.info_label = QLabel("Total: 0 imágenes | Duración estimada: 0s")
        layout.addWidget(self.info_label)

        # Botón de cancelar
        self.cancel_button = QPushButton("Cancelar carga")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_loading)
        layout.addWidget(self.cancel_button)

    def load_thumbnails(self, image_paths, fps=30):
        """Carga miniaturas en un hilo separado"""
        # Cancelar carga anterior si existe
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()

        # Limpiar miniaturas existentes
        self.clear_thumbnails()

        # Actualizar información
        total_images = len(image_paths)
        duration = total_images / fps if fps > 0 else 0
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        self.info_label.setText(
            f"Total: {total_images} imágenes | Duración estimada: {minutes}:{seconds:02d} (a {fps} FPS)")

        # Mostrar botón de cancelar
        self.cancel_button.setVisible(True)

        # Crear y ejecutar cargador de miniaturas
        self.thumbnail_loader = ThumbnailLoader(image_paths)
        self.thumbnail_loader.progress.connect(self.add_thumbnail)
        self.thumbnail_loader.finished.connect(self.loading_finished)

        # Ejecutar en un hilo
        thread = threading.Thread(target=self.thumbnail_loader.run)
        thread.start()

    def add_thumbnail(self, index, thumbnail, image_path):
        """Añade una miniatura a la vista"""
        # Crear botón para la miniatura (en lugar de QLabel)
        thumbnail_button = QPushButton()
        thumbnail_button.setStyleSheet("""
                   QPushButton {
                       border: 1px solid #cccccc;
                       border-radius: 4px;
                       padding: 2px;
                       background-color: #f0f0f0;
                   }
                   QPushButton:hover {
                       border: 2px solid #aaaaaa;
                       background-color: #e0e0e0;
                   }
                   QPushButton:pressed {
                       background-color: #d0d0d0;
                   }
               """)
        thumbnail_button.setIcon(QIcon(thumbnail))
        thumbnail_button.setIconSize(QSize(100, 100))
        thumbnail_button.setFixedSize(110, 110)  # Un poco más grande para el borde
        thumbnail_button.setToolTip(image_path)

        # Conectar el clic del botón
        thumbnail_button.clicked.connect(lambda: self.on_thumbnail_clicked(image_path, thumbnail_button))

        # Añadir a la cuadrícula
        row = index // 5  # 5 columnas
        col = index % 5
        self.grid_layout.addWidget(thumbnail_button, row, col)
        self.thumbnails.append(thumbnail_button)

    def on_thumbnail_clicked(self, image_path, thumbnail_button):
        """Maneja el clic en una miniatura"""
        # Quitar el resaltado anterior
        if self.selected_thumbnail:
            self.selected_thumbnail.setStyleSheet("")

        # Resaltar la miniatura seleccionada
        thumbnail_button.setStyleSheet("border: 2px solid blue;")
        self.selected_thumbnail = thumbnail_button

        # Emitir la señal con la ruta de la imagen
        self.thumbnail_clicked.emit(image_path)

    def loading_finished(self):
        """Maneja la finalización de la carga de miniaturas"""
        self.cancel_button.setVisible(False)

    def cancel_loading(self):
        """Cancela la carga de miniaturas"""
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()
            self.cancel_button.setVisible(False)

    def clear_thumbnails(self):
        """Elimina todas las miniaturas"""
        for thumbnail in self.thumbnails:
            self.grid_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails = []
        self.selected_thumbnail = None