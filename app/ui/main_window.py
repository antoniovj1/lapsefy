import cv2
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QSlider, QSpinBox,
                               QFileDialog, QComboBox, QGroupBox, QStatusBar, QMessageBox,
                               QSplitter, QProgressBar, QApplication)
from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QIcon, QAction
from .preview_widget import PreviewWidget
from .thumbnail_view import ThumbnailView
from .deflicker_dialog import DeflickerDialog
from app.core.image_processor import ImageProcessor
from app.core.video_exporter import VideoExporter
from app.core.deflicker import Deflickerer
import os
import threading
import numpy as np

# --- Eventos Personalizados ---
DeflickerCurveReadyEventType = QEvent.registerEventType()
DeflickerFinishedEventType = QEvent.registerEventType()
DeflickerErrorEventType = QEvent.registerEventType()
PreviewUpdateEventType = QEvent.registerEventType()
StatusUpdateEventType = QEvent.registerEventType()
ExportFinishedEventType = QEvent.registerEventType()


class PreviewUpdateEvent(QEvent):
    def __init__(self, image, filename, width, height):
        super().__init__(QEvent.Type(PreviewUpdateEventType))
        self.image = image
        self.filename = filename
        self.width = width
        self.height = height


class StatusUpdateEvent(QEvent):
    def __init__(self, message, progress=None):
        super().__init__(QEvent.Type(StatusUpdateEventType))
        self.message = message
        self.progress = progress


class ExportFinishedEvent(QEvent):
    def __init__(self, success, message):
        super().__init__(QEvent.Type(ExportFinishedEventType))
        self.success = success
        self.message = message


class DeflickerCurveReadyEvent(QEvent):
    def __init__(self, curve):
        super().__init__(QEvent.Type(DeflickerCurveReadyEventType))
        self.curve = curve


class DeflickerFinishedEvent(QEvent):
    def __init__(self):
        super().__init__(QEvent.Type(DeflickerFinishedEventType))


class DeflickerErrorEvent(QEvent):
    def __init__(self, message):
        super().__init__(QEvent.Type(DeflickerErrorEventType))
        self.message = message


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lapsefy")
        self.setMinimumSize(1200, 800)

        # Variables de estado
        self.image_sequence = []
        self.current_frame_index = 0
        self.processed_sequence = []
        self.deflickerer = Deflickerer()

        # Ajustes actuales
        self.current_exposure = 0.0
        self.current_contrast = 0.0

        # Timer para procesamiento diferido
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.process_current_image_with_adjustments)

        # Inicializar componentes
        self.init_ui()
        self.init_menu()

        # Inicializar procesador
        self.processor = ImageProcessor()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self.preview_widget = PreviewWidget()
        top_layout.addWidget(self.preview_widget, 2)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setAlignment(Qt.AlignTop)

        import_group = QGroupBox("Importar")
        import_layout = QVBoxLayout(import_group)
        self.btn_import = QPushButton("Seleccionar Imágenes")
        self.btn_import.clicked.connect(self.import_images)
        import_layout.addWidget(self.btn_import)
        controls_layout.addWidget(import_group)

        info_group = QGroupBox("Información")
        info_layout = QVBoxLayout(info_group)
        self.image_count_label = QLabel("Imágenes: 0")
        info_layout.addWidget(self.image_count_label)
        self.duration_label = QLabel("Duración estimada: 0s")
        info_layout.addWidget(self.duration_label)
        controls_layout.addWidget(info_group)

        settings_group = QGroupBox("Ajustes")
        settings_layout = QVBoxLayout(settings_group)
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("Exposición:"))
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(-100, 100)
        self.exposure_slider.setValue(0)
        self.exposure_slider.valueChanged.connect(self.slider_changed)
        exposure_layout.addWidget(self.exposure_slider)
        settings_layout.addLayout(exposure_layout)
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("Contraste:"))
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.valueChanged.connect(self.slider_changed)
        contrast_layout.addWidget(self.contrast_slider)
        settings_layout.addLayout(contrast_layout)
        controls_layout.addWidget(settings_group)

        deflicker_group = QGroupBox("Deflickering")
        deflicker_layout = QVBoxLayout(deflicker_group)
        self.btn_deflicker = QPushButton("Aplicar Deflicker")
        self.btn_deflicker.clicked.connect(self.apply_deflicker)
        deflicker_layout.addWidget(self.btn_deflicker)
        controls_layout.addWidget(deflicker_group)

        export_group = QGroupBox("Exportar")
        export_layout = QVBoxLayout(export_group)
        framerate_layout = QHBoxLayout()
        framerate_layout.addWidget(QLabel("FPS:"))
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 60)
        self.fps_spinbox.setValue(30)
        self.fps_spinbox.valueChanged.connect(self.update_estimated_duration)
        framerate_layout.addWidget(self.fps_spinbox)
        export_layout.addLayout(framerate_layout)
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Resolución:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1920x1080", "1280x720", "3840x2160", "Custom"])
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        resolution_layout.addWidget(self.resolution_combo)
        self.custom_width = QSpinBox()
        self.custom_width.setRange(1, 8192);
        self.custom_width.setValue(1920);
        self.custom_width.setVisible(False)
        self.custom_height = QSpinBox()
        self.custom_height.setRange(1, 4320);
        self.custom_height.setValue(1080);
        self.custom_height.setVisible(False)
        resolution_layout.addWidget(QLabel("Ancho:"));
        resolution_layout.addWidget(self.custom_width)
        resolution_layout.addWidget(QLabel("Alto:"));
        resolution_layout.addWidget(self.custom_height)
        export_layout.addLayout(resolution_layout)
        codec_layout = QHBoxLayout()
        codec_layout.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264 (libx264)", "H.265 (libx265)", "MPEG-4", "ProRes"])
        codec_layout.addWidget(self.codec_combo)
        export_layout.addLayout(codec_layout)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Formato:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MOV", "AVI"])
        format_layout.addWidget(self.format_combo)
        export_layout.addLayout(format_layout)
        self.btn_export = QPushButton("Exportar Timelapse")
        self.btn_export.clicked.connect(self.export_timelapse)
        export_layout.addWidget(self.btn_export)
        controls_layout.addWidget(export_group)

        controls_layout.addStretch()

        navigation_layout = QHBoxLayout()
        self.prev_button = QPushButton("Anterior")
        self.prev_button.clicked.connect(self.previous_image)
        self.next_button = QPushButton("Siguiente")
        self.next_button.clicked.connect(self.next_image)
        navigation_layout.addWidget(self.prev_button)
        navigation_layout.addWidget(self.next_button)
        controls_layout.addLayout(navigation_layout)

        top_layout.addWidget(controls_widget, 1)
        top_widget.setLayout(top_layout)

        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.thumbnail_clicked.connect(self.on_thumbnail_clicked)

        splitter.addWidget(top_widget)
        splitter.addWidget(self.thumbnail_view)
        splitter.setSizes([600, 200])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.set_ui_enabled(False)

    def set_ui_enabled(self, enabled):
        for widget in [self.btn_deflicker, self.btn_export, self.exposure_slider,
                       self.contrast_slider, self.fps_spinbox, self.resolution_combo,
                       self.codec_combo, self.format_combo, self.prev_button, self.next_button]:
            widget.setEnabled(enabled)

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Archivo")
        import_action = QAction("Importar Imágenes...", self);
        import_action.triggered.connect(self.import_images)
        export_action = QAction("Exportar Timelapse...", self);
        export_action.triggered.connect(self.export_timelapse)
        exit_action = QAction("Salir", self);
        exit_action.triggered.connect(self.close)
        file_menu.addAction(import_action);
        file_menu.addAction(export_action);
        file_menu.addSeparator();
        file_menu.addAction(exit_action)
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de...", self);
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def import_images(self):
        raw_formats = "*.raw *.RAW *.cr2 *.CR2 *.nef *.NEF *.arw *.ARW *.raf *.RAF"
        jpeg_formats = "*.jpg *.JPG *.jpeg *.JPEG"
        all_supported_filter = f"All Supported Files ({raw_formats} {jpeg_formats})"
        filters = f"{all_supported_filter};;RAW Files ({raw_formats});;JPEG Files ({jpeg_formats});;All Files (*)"
        image_paths, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Imágenes", "", filters)
        if image_paths:
            image_paths.sort()
            self.on_images_loaded(image_paths)

    def on_images_loaded(self, image_sequence):
        if image_sequence:
            self.image_sequence = image_sequence
            self.processed_sequence = []
            self.current_frame_index = 0
            self.processor.clear_cache()

            self.status_bar.showMessage("Cargando miniaturas...")
            self.set_ui_enabled(False)

            self.thumbnail_view.load_thumbnails(self.image_sequence)
            self.thumbnail_view.loading_finished.connect(self.on_thumbnails_ready)

            self.show_current_frame()
            self.update_estimated_duration()
            self.image_count_label.setText(f"Imágenes: {len(self.image_sequence)}")
        else:
            QMessageBox.warning(self, "Sin Imágenes", "No se seleccionaron imágenes válidas.")

    def on_thumbnails_ready(self):
        self.status_bar.showMessage(f"Cargadas {len(self.image_sequence)} imágenes.", 5000)
        self.set_ui_enabled(True)
        self.update_navigation_buttons()
        self.highlight_current_thumbnail()

    def update_navigation_buttons(self):
        has_images = bool(self.image_sequence)
        self.prev_button.setEnabled(has_images and self.current_frame_index > 0)
        self.next_button.setEnabled(has_images and self.current_frame_index < len(self.image_sequence) - 1)

    def slider_changed(self):
        self.current_exposure = self.exposure_slider.value() / 100.0
        self.current_contrast = self.contrast_slider.value() / 100.0
        self.preview_timer.stop()
        self.preview_timer.start(200)

    def process_current_image_with_adjustments(self):
        if not self.image_sequence: return
        image_path = self.image_sequence[self.current_frame_index]

        base_image = None
        if self.processed_sequence and self.current_frame_index < len(self.processed_sequence):
            base_image = self.processed_sequence[self.current_frame_index]
        else:
            base_image = self.processor.load_image(image_path, use_cache=True)

        if base_image is not None:
            threading.Thread(target=self.process_preview_image,
                             args=(base_image, self.current_exposure, self.current_contrast),
                             daemon=True).start()

    def process_preview_image(self, base_image, exposure, contrast):
        try:
            processed_image = self.processor.adjust_image_from_array(base_image, exposure, contrast)
            filename = os.path.basename(self.image_sequence[self.current_frame_index])
            if processed_image is not None:
                QApplication.instance().postEvent(
                    self,
                    PreviewUpdateEvent(processed_image, filename,
                                       processed_image.shape[1], processed_image.shape[0])
                )
        except Exception as e:
            print(f"Error en procesamiento de previsualización: {e}")

    def on_thumbnail_clicked(self, image_path):
        try:
            index = self.image_sequence.index(image_path)
            if index != self.current_frame_index:
                self.current_frame_index = index
                self.show_current_frame()
        except ValueError:
            pass

    def show_current_frame(self):
        if not self.image_sequence: return

        for slider in [self.exposure_slider, self.contrast_slider]:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self.current_exposure = 0.0
        self.current_contrast = 0.0

        image_path = self.image_sequence[self.current_frame_index]

        if not self.processor.is_in_cache(image_path):
            self.preview_widget.show_loading()

        threading.Thread(target=self.load_and_display_image, args=(image_path,), daemon=True).start()

        self.highlight_current_thumbnail()
        self.update_navigation_buttons()

    def load_and_display_image(self, image_path):
        base_image = self.processor.load_image(image_path, use_cache=True)
        if base_image is not None:
            filename = os.path.basename(image_path)
            QApplication.instance().postEvent(
                self,
                PreviewUpdateEvent(base_image, filename, base_image.shape[1], base_image.shape[0])
            )

    def highlight_current_thumbnail(self):
        if self.image_sequence:
            self.thumbnail_view.highlight_thumbnail(self.current_frame_index)

    def next_image(self):
        if self.current_frame_index < len(self.image_sequence) - 1:
            self.current_frame_index += 1
            self.show_current_frame()

    def previous_image(self):
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.show_current_frame()

    def update_estimated_duration(self):
        if self.image_sequence:
            fps = self.fps_spinbox.value()
            total_images = len(self.image_sequence)
            duration = total_images / fps if fps > 0 else 0
            minutes, seconds = divmod(int(duration), 60)
            self.duration_label.setText(f"Duración estimada: {minutes:02d}:{seconds:02d} (a {fps} FPS)")

    def on_resolution_changed(self, text):
        is_custom = text == "Custom"
        self.custom_width.setVisible(is_custom)
        self.custom_height.setVisible(is_custom)

    def show_about(self):
        QMessageBox.about(self, "Acerca de Lapsefy",
                          "Lapsefy v1.1\n\nUna aplicación para crear timelapses a partir de secuencias de imágenes.")

    def customEvent(self, event):
        event_type = event.type()
        if event_type == PreviewUpdateEventType:
            self.preview_widget.set_image(event.image, event.filename, event.width, event.height)
        elif event_type == StatusUpdateEventType:
            self.status_bar.showMessage(event.message)
            if event.progress is not None:
                self.progress_bar.setValue(event.progress)
        elif event_type == ExportFinishedEventType:
            self.handle_export_finished(event.success, event.message)
        elif event_type == DeflickerCurveReadyEventType:
            self.handle_curve_ready(event.curve)
        elif event_type == DeflickerFinishedEventType:
            self.handle_deflicker_finished()
        elif event_type == DeflickerErrorEventType:
            self.handle_deflicker_error(event.message)

    def apply_deflicker(self):
        if not self.image_sequence:
            QMessageBox.warning(self, "Advertencia", "Primero debe importar una secuencia de imágenes.")
            return

        self.status_bar.showMessage("Analizando brillo de la secuencia...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.set_ui_enabled(False)

        self.deflickerer.progress_updated.connect(self.update_progress)

        def calculate_curve_thread():
            try:
                curve = self.deflickerer.get_brightness_curve(self.image_sequence)
                QApplication.instance().postEvent(self, DeflickerCurveReadyEvent(curve))
            except Exception as e:
                error_message = f"Error al calcular la curva de brillo: {e}"
                QApplication.instance().postEvent(self, DeflickerErrorEvent(error_message))

        threading.Thread(target=calculate_curve_thread, daemon=True).start()

    def update_progress(self, value):
        if self.progress_bar.isVisible():
            self.progress_bar.setValue(value)

    def handle_curve_ready(self, curve):
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Análisis de brillo completado.")
        self.set_ui_enabled(True)

        if not curve:
            QMessageBox.critical(self, "Error", "No se pudo generar la curva de brillo.")
            return

        dialog = DeflickerDialog(curve, self)
        if dialog.exec():
            smoothing_level = dialog.get_smoothing_level()
            self.status_bar.showMessage("Aplicando corrección de deflicker...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.set_ui_enabled(False)

            def apply_correction_thread():
                try:
                    smoothed_curve = self.deflickerer.get_smoothed_curve(smoothing_level)
                    self.processed_sequence = self.deflickerer.apply_correction(self.image_sequence, smoothed_curve)
                    QApplication.instance().postEvent(self, DeflickerFinishedEvent())
                except Exception as e:
                    error_message = f"Error al aplicar la corrección: {e}"
                    QApplication.instance().postEvent(self, DeflickerErrorEvent(error_message))

            threading.Thread(target=apply_correction_thread, daemon=True).start()

    def handle_deflicker_finished(self):
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Deflicker aplicado correctamente.", 5000)
        self.set_ui_enabled(True)
        QMessageBox.information(self, "Éxito", "El proceso de deflicker ha finalizado correctamente.")
        self.show_current_frame()

    def handle_deflicker_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Error en el proceso de deflicker.", 5000)
        self.set_ui_enabled(True)
        QMessageBox.critical(self, "Error de Deflicker", error_message)

    def export_timelapse(self):
        if not self.image_sequence:
            QMessageBox.warning(self, "Error", "No hay imágenes para exportar")
            return

        format_ext = {"MP4": "mp4", "MOV": "mov", "AVI": "avi"}
        selected_format = self.format_combo.currentText()
        file_extension = format_ext.get(selected_format, "mp4")

        output_path, _ = QFileDialog.getSaveFileName(self, "Guardar timelapse", f"timelapse.{file_extension}",
                                                     f"{selected_format} files (*.{file_extension})")

        if output_path:
            if not output_path.lower().endswith(f".{file_extension}"):
                output_path += f".{file_extension}"

            self.progress_bar.setVisible(True)
            self.set_ui_enabled(False)
            self.status_bar.showMessage("Exportando timelapse...")

            fps = self.fps_spinbox.value()
            resolution_text = self.resolution_combo.currentText()
            resolution = f"{self.custom_width.value()}x{self.custom_height.value()}" if resolution_text == "Custom" else resolution_text

            codec_map = {"H.264 (libx264)": "libx264", "H.265 (libx265)": "libx265", "MPEG-4": "mpeg4",
                         "ProRes": "prores"}
            codec = codec_map.get(self.codec_combo.currentText(), "libx264")

            sequence_to_export = self.processed_sequence if self.processed_sequence else self.image_sequence
            is_path_sequence = not bool(self.processed_sequence)

            threading.Thread(target=self.process_and_export,
                             args=(output_path, fps, resolution, codec, sequence_to_export, is_path_sequence),
                             daemon=True).start()

    def process_and_export(self, output_path, fps, resolution, codec, image_sequence, is_path_sequence):
        try:
            final_sequence = []
            if is_path_sequence:
                total = len(image_sequence)
                for i, path in enumerate(image_sequence):
                    QApplication.instance().postEvent(self, StatusUpdateEvent(f"Procesando {i + 1}/{total}",
                                                                              int(((i + 1) / total) * 50)))
                    img = self.processor.adjust_image(path, self.current_exposure, self.current_contrast)
                    if img is not None:
                        final_sequence.append(img)
            else:
                final_sequence = image_sequence
                QApplication.instance().postEvent(self, StatusUpdateEvent("Preparando para exportar...", 50))

            exporter = VideoExporter()
            success = exporter.export_video(final_sequence, output_path, fps, resolution, codec)
            message = "Timelapse exportado correctamente" if success else "Error al exportar"
            QApplication.instance().postEvent(self, ExportFinishedEvent(success, message))
        except Exception as e:
            QApplication.instance().postEvent(self, ExportFinishedEvent(False, f"Error durante exportación: {str(e)}"))

    def handle_export_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.set_ui_enabled(True)
        if success:
            self.status_bar.showMessage(message, 5000)
            QMessageBox.information(self, "Éxito", message)
        else:
            self.status_bar.showMessage("Error al exportar", 5000)
            QMessageBox.critical(self, "Error", message)
