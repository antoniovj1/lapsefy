from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
                               QFileDialog, QComboBox, QGroupBox, QStatusBar, QMessageBox,
                               QSplitter, QProgressBar, QApplication)
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QIcon, QAction
from .preview_widget import PreviewWidget
from .thumbnail_view import ThumbnailView
from app.core.image_processor import ImageProcessor
from app.core.video_exporter import VideoExporter
from app.core.export_thread import ExportThread
from app.core.deflicker import Deflickerer
from app.core.image_loader import ImageLoader  # Añadir esta importación
from app.core.image_processor_thread import ImageProcessorThread  # Añadir esta importación
import time
import os
import threading


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timelapse Creator")
        self.setMinimumSize(1200, 800)

        # Variables de estado
        self.image_sequence = []
        self.current_frame_index = 0
        self.processed_sequence = []  # Solo se usará durante la exportación

        # Ajustes actuales
        self.current_exposure = 0.0
        self.current_contrast = 0.0

        # Inicializar componentes
        self.init_ui()
        self.init_menu()

        # Inicializar procesador
        self.processor = ImageProcessor()
        self.processor_thread = ImageProcessorThread()
        self.processor_thread.processing_done.connect(self.on_processing_done)
        self.processor_thread.processing_error.connect(self.on_processing_error)
        self.last_processing_time = 0
        self.pending_processing = False
        self.current_processing_id = 0

    def init_ui(self):
        # Widget central y layout principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Splitter para dividir la ventana
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # Panel superior (previsualización y controles)
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        # Panel de previsualización
        self.preview_widget = PreviewWidget()
        top_layout.addWidget(self.preview_widget, 2)

        # Panel de controles
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setAlignment(Qt.AlignTop)

        # Grupo de importación
        import_group = QGroupBox("Importar")
        import_layout = QVBoxLayout(import_group)

        self.btn_import = QPushButton("Seleccionar carpeta de imágenes")
        self.btn_import.clicked.connect(self.import_images)
        import_layout.addWidget(self.btn_import)

        controls_layout.addWidget(import_group)

        # Grupo de información
        info_group = QGroupBox("Información")
        info_layout = QVBoxLayout(info_group)

        self.image_count_label = QLabel("Imágenes: 0")
        info_layout.addWidget(self.image_count_label)

        self.duration_label = QLabel("Duración estimada: 0s")
        info_layout.addWidget(self.duration_label)

        controls_layout.addWidget(info_group)

        # Grupo de ajustes
        settings_group = QGroupBox("Ajustes")
        settings_layout = QVBoxLayout(settings_group)

        # Exposición
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("Exposición:"))
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(-100, 100)
        self.exposure_slider.setValue(0)

        self.exposure_slider.valueChanged.connect(self.update_preview_only)
        exposure_layout.addWidget(self.exposure_slider)
        settings_layout.addLayout(exposure_layout)

        # Contraste
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("Contraste:"))
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)

        self.contrast_slider.valueChanged.connect(self.update_preview_only)
        contrast_layout.addWidget(self.contrast_slider)
        settings_layout.addLayout(contrast_layout)

        controls_layout.addWidget(settings_group)

        # Grupo de deflickering
        deflicker_group = QGroupBox("Deflickering")
        deflicker_layout = QVBoxLayout(deflicker_group)

        self.btn_deflicker = QPushButton("Aplicar Deflicker")
        self.btn_deflicker.clicked.connect(self.apply_deflicker)
        deflicker_layout.addWidget(self.btn_deflicker)

        controls_layout.addWidget(deflicker_group)

        # Grupo de exportación
        export_group = QGroupBox("Exportar")
        export_layout = QVBoxLayout(export_group)

        # Framerate
        framerate_layout = QHBoxLayout()
        framerate_layout.addWidget(QLabel("FPS:"))
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 60)
        self.fps_spinbox.setValue(30)
        self.fps_spinbox.valueChanged.connect(self.update_estimated_duration)
        framerate_layout.addWidget(self.fps_spinbox)
        export_layout.addLayout(framerate_layout)

        # Resolución
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Resolución:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1920x1080", "1280x720", "3840x2160", "Custom"])
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        resolution_layout.addWidget(self.resolution_combo)

        # Campos para resolución personalizada
        self.custom_width = QSpinBox()
        self.custom_width.setRange(1, 8192)
        self.custom_width.setValue(1920)
        self.custom_width.setVisible(False)

        self.custom_height = QSpinBox()
        self.custom_height.setRange(1, 4320)
        self.custom_height.setValue(1080)
        self.custom_height.setVisible(False)

        resolution_layout.addWidget(QLabel("Ancho:"))
        resolution_layout.addWidget(self.custom_width)
        resolution_layout.addWidget(QLabel("Alto:"))
        resolution_layout.addWidget(self.custom_height)
        export_layout.addLayout(resolution_layout)

        # Codec
        codec_layout = QHBoxLayout()
        codec_layout.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264 (libx264)", "H.265 (libx265)", "MPEG-4", "ProRes"])
        codec_layout.addWidget(self.codec_combo)
        export_layout.addLayout(codec_layout)

        # Formato
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

        top_layout.addWidget(controls_widget, 1)

        # Panel inferior (miniaturas)
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.thumbnail_clicked.connect(self.on_thumbnail_clicked)


        # Añadir widgets al splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(self.thumbnail_view)

        # Configurar proporciones del splitter
        splitter.setSizes([400, 200])

        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Barra de progreso y botón de cancelar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_export)
        self.status_bar.addPermanentWidget(self.cancel_button)

        # Botones de navegación
        navigation_layout = QHBoxLayout()
        self.prev_button = QPushButton("Anterior")
        self.prev_button.clicked.connect(self.previous_image)
        self.next_button = QPushButton("Siguiente")
        self.next_button.clicked.connect(self.next_image)

        navigation_layout.addWidget(self.prev_button)
        navigation_layout.addWidget(self.next_button)
        controls_layout.addLayout(navigation_layout)

        # Deshabilitar botones hasta que se carguen imágenes
        self.set_ui_enabled(False)

    def set_ui_enabled(self, enabled):
        """Habilita o deshabilita los controles de la UI"""
        self.btn_deflicker.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)
        self.exposure_slider.setEnabled(enabled)
        self.contrast_slider.setEnabled(enabled)
        self.fps_spinbox.setEnabled(enabled)
        self.resolution_combo.setEnabled(enabled)
        self.codec_combo.setEnabled(enabled)
        self.format_combo.setEnabled(enabled)

    def init_menu(self):
        menubar = self.menuBar()

        # Menú Archivo
        file_menu = menubar.addMenu("Archivo")

        import_action = QAction("Importar", self)
        import_action.triggered.connect(self.import_images)
        file_menu.addAction(import_action)

        export_action = QAction("Exportar", self)
        export_action.triggered.connect(self.export_timelapse)
        file_menu.addAction(export_action)

        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Menú Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def import_images(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de imágenes")
        if folder:
            # Mostrar barra de progreso
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage("Cargando imágenes...")
            self.set_ui_enabled(False)

            # Cargar imágenes en un hilo separado
            self.image_loader = ImageLoader()
            self.image_loader.progress_updated.connect(self.update_loading_progress)
            self.image_loader.finished.connect(self.on_images_loaded)

            # Ejecutar en un hilo
            thread = threading.Thread(target=self.image_loader.load_images, args=(folder,))
            thread.start()

    def update_loading_progress(self, progress, message):
        """Actualiza la barra de progreso durante la carga"""
        self.progress_bar.setValue(progress)
        self.status_bar.showMessage(message)

    def on_images_loaded(self, image_sequence):
        """Maneja la finalización de la carga de imágenes"""
        self.progress_bar.setVisible(False)

        if image_sequence:
            self.image_sequence = image_sequence
            self.current_frame_index = 0
            self.show_current_frame()

            # Actualizar información
            fps = self.fps_spinbox.value()
            total_images = len(self.image_sequence)
            duration = total_images / fps if fps > 0 else 0
            minutes = int(duration // 60)
            seconds = int(duration % 60)

            self.image_count_label.setText(f"Imágenes: {total_images}")
            self.duration_label.setText(f"Duración estimada: {minutes}:{seconds:02d} (a {fps} FPS)")

            # Cargar miniaturas
            self.thumbnail_view.load_thumbnails(self.image_sequence, fps)
            self.status_bar.showMessage(f"Cargadas {len(self.image_sequence)} imágenes")

            # Habilitar UI
            self.set_ui_enabled(True)
        else:
            QMessageBox.warning(self, "Error", "No se encontraron imágenes válidas en la carpeta seleccionada")
            self.status_bar.showMessage("No se encontraron imágenes válidas")

    def load_image_sequence(self, folder):
        supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.raw', '.cr2', '.nef', '.arw']
        image_files = []

        for file in os.listdir(folder):
            if any(file.lower().endswith(ext) for ext in supported_formats):
                image_files.append(os.path.join(folder, file))

        return sorted(image_files)

    def update_navigation_buttons(self):
        """Actualiza el estado de los botones de navegación"""
        has_images = bool(self.image_sequence)
        self.prev_button.setEnabled(has_images and self.current_frame_index > 0)
        self.next_button.setEnabled(has_images and self.current_frame_index < len(self.image_sequence) - 1)

    def apply_adjustments(self):
        if self.image_sequence:
            exposure = self.exposure_slider.value() / 100.0
            contrast = self.contrast_slider.value() / 100.0

            # Procesar imagen actual con los ajustes
            processor = ImageProcessor()
            adjusted_image = processor.adjust_image(
                self.image_sequence[self.current_frame_index],
                exposure,
                contrast
            )

            self.preview_widget.set_image(adjusted_image)

    def on_thumbnail_clicked(self, image_path):
        """Maneja el clic en una miniatura para mostrar la imagen en grande"""
        # Encontrar el índice de la imagen en la secuencia
        try:
            index = self.image_sequence.index(image_path)
            self.current_frame_index = index
            self.show_current_frame()
        except ValueError:
            # Si no se encuentra la ruta (no debería pasar), mostrar mensaje de error
            QMessageBox.warning(self, "Error", "No se pudo cargar la imagen seleccionada")

    def apply_deflicker(self):
        if not self.image_sequence:
            QMessageBox.warning(self, "Error", "Primero debe importar una secuencia de imágenes")
            return

        self.status_bar.showMessage("Aplicando deflicker...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_deflicker.setEnabled(False)

        # Procesar deflickering
        self.deflickerer = Deflickerer()
        self.deflickerer.progress_updated.connect(self.update_progress)

        # Ejecutar en un hilo para no bloquear la UI
        def deflicker_thread():
            try:
                self.processed_sequence = self.deflickerer.process_sequence(self.image_sequence)
                self.deflicker_finished()
            except Exception as e:
                self.deflicker_error(str(e))

        thread = threading.Thread(target=deflicker_thread)
        thread.start()

    def deflicker_finished(self):
        self.progress_bar.setVisible(False)
        self.btn_deflicker.setEnabled(True)
        self.status_bar.showMessage("Deflicker aplicado correctamente")
        self.show_current_frame()

    def deflicker_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.btn_deflicker.setEnabled(True)
        self.status_bar.showMessage("Error al aplicar deflicker")
        QMessageBox.critical(self, "Error", f"Error al aplicar deflicker: {error_msg}")

    def update_estimated_duration(self):
        if self.image_sequence:
            fps = self.fps_spinbox.value()
            total_images = len(self.image_sequence)
            duration = total_images / fps if fps > 0 else 0
            minutes = int(duration // 60)
            seconds = int(duration % 60)

            self.duration_label.setText(f"Duración estimada: {minutes}:{seconds:02d} (a {fps} FPS)")
            self.thumbnail_view.load_thumbnails(self.image_sequence, fps)

    def on_resolution_changed(self, text):
        if text == "Custom":
            self.custom_width.setVisible(True)
            self.custom_height.setVisible(True)
        else:
            self.custom_width.setVisible(False)
            self.custom_height.setVisible(False)

    def export_timelapse(self):
        if not self.image_sequence:
            QMessageBox.warning(self, "Error", "No hay imágenes para exportar")
            return

        # Determinar la extensión basada en el formato seleccionado
        format_ext = {
            "MP4": "mp4",
            "MOV": "mov",
            "AVI": "avi"
        }
        selected_format = self.format_combo.currentText()
        file_extension = format_ext.get(selected_format, "mp4")

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar timelapse",
            f"timelapse.{file_extension}",
            f"{selected_format} files (*.{file_extension})"
        )

        if output_path:
            # Asegurarse de que la extensión es correcta
            if not output_path.lower().endswith(f".{file_extension}"):
                output_path = f"{output_path}.{file_extension}"

            self.progress_bar.setVisible(True)
            self.cancel_button.setVisible(True)
            self.btn_export.setEnabled(False)

            self.status_bar.showMessage("Exportando timelapse...")

            # Obtener configuración de exportación
            fps = self.fps_spinbox.value()
            resolution = self.resolution_combo.currentText()
            if resolution == "Custom":
                # Usar los valores personalizados
                width = self.custom_width.value()
                height = self.custom_height.value()
                resolution = f"{width}x{height}"

            # Mapear codec
            codec_map = {
                "H.264 (libx264)": "libx264",
                "H.265 (libx265)": "libx265",
                "MPEG-4": "mpeg4",
                "ProRes": "prores"
            }
            codec = codec_map.get(self.codec_combo.currentText(), "libx264")

            # Procesar toda la secuencia con los ajustes actuales (solo durante la exportación)
            # Esto se hace en un hilo separado para no bloquear la UI
            threading.Thread(target=self.process_and_export,
                             args=(output_path, fps, resolution, codec)).start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def process_and_export(self, output_path, fps, resolution, codec):
        """Procesa la secuencia completa y exporta el video en un hilo secundario"""
        try:
            # Mostrar progreso de procesamiento
            QApplication.instance().postEvent(
                self,
                StatusUpdateEvent("Procesando imágenes con ajustes...", 0)
            )

            # Procesar toda la secuencia con los ajustes actuales
            processed_sequence = self.processor.process_sequence(
                self.image_sequence,
                self.current_exposure,
                self.current_contrast
            )

            # Actualizar progreso
            QApplication.instance().postEvent(
                self,
                StatusUpdateEvent("Exportando video...", 50)
            )

            # Exportar video
            exporter = VideoExporter()
            success = exporter.export_video(processed_sequence, output_path, fps, resolution, codec)

            # Notificar finalización
            QApplication.instance().postEvent(
                self,
                ExportFinishedEvent(success, "Timelapse exportado correctamente" if success else "Error al exportar")
            )

        except Exception as e:
            QApplication.instance().postEvent(
                self,
                ExportFinishedEvent(False, f"Error durante exportación: {str(e)}")
            )

    def export_finished(self, success):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.btn_export.setEnabled(True)

        if success:
            self.status_bar.showMessage("Timelapse exportado correctamente")
            QMessageBox.information(self, "Éxito", "Timelapse exportado correctamente")
        else:
            self.status_bar.showMessage("Error al exportar el timelapse")

    def export_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.btn_export.setEnabled(True)

        QMessageBox.critical(self, "Error", f"Error al exportar: {error_message}")
        self.status_bar.showMessage("Error al exportar el timelapse")

    def cancel_export(self):
        if hasattr(self, 'export_thread') and self.export_thread.isRunning():
            self.export_thread.terminate()
            self.export_thread.wait()
            self.progress_bar.setVisible(False)
            self.cancel_button.setVisible(False)
            self.btn_export.setEnabled(True)
            self.status_bar.showMessage("Exportación cancelada")

    def show_about(self):
        QMessageBox.about(self, "Acerca de Timelapse Creator",
                          "Timelapse Creator v0.1\n\n"
                          "Una aplicación para crear timelapses a partir de secuencias de imágenes RAW o JPEG.")

    def keyPressEvent(self, event):
        """Maneja eventos de teclado para navegar entre imágenes"""
        if not self.image_sequence:
            return

        if event.key() == Qt.Key_Left:
            self.previous_image()
        elif event.key() == Qt.Key_Right:
            self.next_image()
        else:
            super().keyPressEvent(event)

    def next_image(self):
        """Muestra la siguiente imagen en la secuencia"""
        if self.image_sequence and self.current_frame_index < len(self.image_sequence) - 1:
            self.current_frame_index += 1
            self.show_current_frame()
            self.highlight_current_thumbnail()

    def previous_image(self):
        """Muestra la imagen anterior en la secuencia"""
        if self.image_sequence and self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.show_current_frame()
            self.highlight_current_thumbnail()

    def highlight_current_thumbnail(self):
        """Resalta la miniatura correspondiente a la imagen actual"""
        if not self.image_sequence or self.current_frame_index >= len(self.image_sequence):
            return

        current_image_path = self.image_sequence[self.current_frame_index]

        # Buscar el botón de miniatura correspondiente
        for thumbnail_button in self.thumbnail_view.thumbnails:
            if thumbnail_button.toolTip() == current_image_path:
                # Quitar el resaltado anterior
                if self.thumbnail_view.selected_thumbnail:
                    self.thumbnail_view.selected_thumbnail.setStyleSheet("")

                # Resaltar la miniatura actual
                thumbnail_button.setStyleSheet("border: 2px solid blue;")
                self.thumbnail_view.selected_thumbnail = thumbnail_button

                # Desplazar la vista para que sea visible
                self.thumbnail_view.scroll_area.ensureWidgetVisible(thumbnail_button)
                break

    def schedule_processing(self):
        """Programa el procesamiento de la imagen con un pequeño retraso"""
        if not self.image_sequence:
            return

        # Incrementar el ID de procesamiento
        self.current_processing_id += 1
        current_id = self.current_processing_id

        # Usar un temporizador para procesar después de una pausa en los ajustes
        current_time = time.time()

        # Si ha pasado menos de 0.1 segundos desde el último cambio, esperar
        if current_time - self.last_processing_time < 0.1:
            self.pending_processing = True
            # Usar un QTimer para procesar después de una pausa
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.process_image_delayed(current_id))
        else:
            self.process_image(current_id)

        self.last_processing_time = current_time

    def process_image_delayed(self, processing_id):
        """Procesa la imagen después de una pausa en los ajustes"""
        if self.pending_processing and processing_id == self.current_processing_id:
            self.process_image(processing_id)
            self.pending_processing = False

    def process_image(self, processing_id):
        """Inicia el procesamiento de la imagen en segundo plano"""
        if not self.image_sequence or self.current_frame_index >= len(self.image_sequence):
            return

        # Obtener los valores actuales de los sliders
        exposure = self.exposure_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0

        # Configurar y ejecutar el hilo de procesamiento
        image_path = self.image_sequence[self.current_frame_index]
        self.processor_thread.set_parameters(image_path, exposure, contrast, processing_id)

        # Solo iniciar el hilo si no está en ejecución
        if not self.processor_thread.isRunning():
            self.processor_thread.start()

    def on_processing_done(self, result):
        """Maneja la finalización del procesamiento de la imagen"""
        processed_image, processing_id = result

        # Solo actualizar si este es el resultado más reciente
        if processing_id == self.current_processing_id:
            self.preview_widget.set_image(processed_image)

    def on_processing_error(self, error_message):
        """Maneja errores en el procesamiento de la imagen"""
        self.status_bar.showMessage(error_message)

    def update_preview_only(self):
        """Actualiza solo la previsualización con los ajustes actuales"""
        if not self.image_sequence:
            return

        # Obtener valores actuales
        exposure = self.exposure_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0

        # Guardar para usar durante la exportación
        self.current_exposure = exposure
        self.current_contrast = contrast

        # Procesar solo la imagen actual para previsualización
        self.update_current_preview()

    def update_current_preview(self):
        """Actualiza la previsualización de la imagen actual con los ajustes"""
        if not self.image_sequence or self.current_frame_index >= len(self.image_sequence):
            return

        image_path = self.image_sequence[self.current_frame_index]

        try:
            # Cargar y procesar la imagen actual
            exposure = self.current_exposure
            contrast = self.current_contrast

            # Procesar en un hilo para no bloquear la UI
            threading.Thread(target=self.process_preview_image,
                             args=(image_path, exposure, contrast)).start()
        except Exception as e:
            print(f"Error al actualizar previsualización: {e}")

    def process_preview_image(self, image_path, exposure, contrast):
        """Procesa una imagen para previsualización en un hilo secundario"""
        try:
            # Procesar la imagen
            processed_image = self.processor.adjust_image(image_path, exposure, contrast)

            # Actualizar la UI en el hilo principal
            if processed_image is not None:
                QApplication.instance().postEvent(
                    self,
                    PreviewUpdateEvent(processed_image, os.path.basename(image_path),
                                       processed_image.shape[1], processed_image.shape[0])
                )
        except Exception as e:
            print(f"Error en procesamiento de previsualización: {e}")

    def show_current_frame(self):
        if self.image_sequence and self.current_frame_index < len(self.image_sequence):
            image_path = self.image_sequence[self.current_frame_index]
            self.preview_widget.load_image(image_path)
            self.highlight_current_thumbnail()

            # Reiniciar los sliders a cero cuando cambiamos de imagen
            self.exposure_slider.setValue(0)
            self.contrast_slider.setValue(0)
            self.current_exposure = 0.0
            self.current_contrast = 0.0

    def customEvent(self, event):
        """Maneja eventos personalizados para comunicación entre hilos"""
        if isinstance(event, PreviewUpdateEvent):
            # Actualizar previsualización con imagen procesada
            self.preview_widget.set_image(event.image, event.filename, event.width, event.height)

        elif isinstance(event, StatusUpdateEvent):
            # Actualizar barra de estado y progreso
            self.status_bar.showMessage(event.message)
            self.progress_bar.setValue(event.progress)

        elif isinstance(event, ExportFinishedEvent):
            # Finalizar exportación
            self.progress_bar.setVisible(False)
            self.cancel_button.setVisible(False)
            self.btn_export.setEnabled(True)

            if event.success:
                self.status_bar.showMessage(event.message)
                QMessageBox.information(self, "Éxito", event.message)
            else:
                self.status_bar.showMessage("Error al exportar")
                QMessageBox.critical(self, "Error", event.message)

# Eventos personalizados para comunicación entre hilos
class PreviewUpdateEvent(QEvent):
    def __init__(self, image, filename, width, height):
        super().__init__(QEvent.Type(UserEvent))
        self.image = image
        self.filename = filename
        self.width = width
        self.height = height

class StatusUpdateEvent(QEvent):
    def __init__(self, message, progress):
        super().__init__(QEvent.Type(UserEvent + 1))
        self.message = message
        self.progress = progress

class ExportFinishedEvent(QEvent):
    def __init__(self, success, message):
        super().__init__(QEvent.Type(UserEvent + 2))
        self.success = success
        self.message = message

# Definir tipos de eventos personalizados
UserEvent = QEvent.Type(QEvent.registerEventType())