# app/ui/thumbnail_view.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QScrollArea,
                               QGridLayout, QPushButton)
from PySide6.QtCore import Qt, QSize, Signal, QObject
from PySide6.QtGui import QPixmap, QImage, QIcon
import cv2
import numpy as np
import threading
import rawpy


class ThumbnailLoader(QObject):
    progress = Signal(int, QPixmap, str)
    finished = Signal()

    def __init__(self, image_paths, thumbnail_size=100):
        super().__init__()
        self.image_paths = image_paths
        self.thumbnail_size = thumbnail_size
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        """Carga miniaturas en un hilo separado, con soporte para RAW."""
        raw_extensions = ['.raw', '.cr2', '.nef', '.arw', '.raf']
        for i, image_path in enumerate(self.image_paths):
            if self._is_cancelled:
                break
            try:
                image = None
                if any(image_path.lower().endswith(ext) for ext in raw_extensions):
                    with rawpy.imread(image_path) as raw:
                        try:
                            # Intenta extraer la miniatura incrustada (mucho más rápido)
                            thumb = raw.extract_thumb()
                            if thumb.format == rawpy.ThumbFormat.JPEG:
                                image_data = np.frombuffer(thumb.data, np.uint8)
                                image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
                        except rawpy.LibRawNoThumbnailError:
                            # Si no hay miniatura, procesa la imagen (más lento)
                            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
                            image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                else:
                    image = cv2.imread(image_path)

                if image is not None:
                    thumbnail = self.create_thumbnail(image)
                    self.progress.emit(i, thumbnail, image_path)
            except Exception as e:
                print(f"Error al cargar miniatura para {image_path}: {e}")

        # Emite la señal de finalización incluso si se cancela
        self.finished.emit()

    def create_thumbnail(self, image):
        """Crea una miniatura a partir de una imagen de OpenCV."""
        height, width = image.shape[:2]
        max_size = self.thumbnail_size
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

        rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        return QPixmap.fromImage(qt_image)


class ThumbnailView(QWidget):
    thumbnail_clicked = Signal(str)
    loading_finished = Signal()  # Señal para notificar a la ventana principal

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thumbnails = []
        self.thumbnail_loader_thread = None
        self.thumbnail_loader = None
        self.selected_thumbnail = None
        self.default_stylesheet = """
            QPushButton { border: 1px solid #cccccc; border-radius: 4px; padding: 2px; background-color: #f0f0f0; }
            QPushButton:hover { border: 2px solid #aaaaaa; background-color: #e0e0e0; }
        """
        self.highlight_stylesheet = "border: 2px solid #0078d7;"

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def load_thumbnails(self, image_paths, fps=30):
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()
        self.clear_thumbnails()

        self.thumbnail_loader = ThumbnailLoader(image_paths)
        self.thumbnail_loader.progress.connect(self.add_thumbnail)
        self.thumbnail_loader.finished.connect(self.loading_finished)

        self.thumbnail_loader_thread = threading.Thread(target=self.thumbnail_loader.run)
        self.thumbnail_loader_thread.start()

    def add_thumbnail(self, index, thumbnail, image_path):
        thumbnail_button = QPushButton()
        thumbnail_button.setStyleSheet(self.default_stylesheet)
        thumbnail_button.setIcon(QIcon(thumbnail))
        thumbnail_button.setIconSize(QSize(100, 100))
        thumbnail_button.setFixedSize(110, 110)
        thumbnail_button.setToolTip(image_path)
        thumbnail_button.clicked.connect(lambda: self.on_thumbnail_clicked(image_path))

        row, col = divmod(index, 8)  # Aumentado a 8 columnas para aprovechar mejor el espacio
        self.grid_layout.addWidget(thumbnail_button, row, col)
        self.thumbnails.append(thumbnail_button)

    def on_thumbnail_clicked(self, image_path):
        self.thumbnail_clicked.emit(image_path)

    def highlight_thumbnail(self, index):
        if not (0 <= index < len(self.thumbnails)):
            return

        if self.selected_thumbnail:
            self.selected_thumbnail.setStyleSheet(self.default_stylesheet)

        thumbnail_button = self.thumbnails[index]
        thumbnail_button.setStyleSheet(self.highlight_stylesheet)
        self.selected_thumbnail = thumbnail_button
        self.scroll_area.ensureWidgetVisible(thumbnail_button)

    def cancel_loading(self):
        if self.thumbnail_loader:
            self.thumbnail_loader.cancel()

    def clear_thumbnails(self):
        for thumbnail in self.thumbnails:
            self.grid_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()
        self.selected_thumbnail = None
