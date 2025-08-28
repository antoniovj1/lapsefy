# app/ui/deflicker_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QSlider, QLabel, QGroupBox, QComboBox, QSplitter,
                               QToolButton, QCheckBox, QSpinBox, QTabWidget, QWidget,
                               QFileDialog, QMessageBox, QDoubleSpinBox)
from PySide6.QtCore import Qt, QPoint, Signal, QObject
from PySide6.QtGui import QImage, QPixmap, QCursor
import pyqtgraph as pg
import numpy as np
from scipy import signal
import json
import os
import threading
import rawpy
import cv2
import time


class ReadOnlyPlotWidget(pg.PlotWidget):
    """PlotWidget personalizado de solo lectura para evitar interacciones no deseadas"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        # Ignorar completamente la rueda del ratón
        event.ignore()

    def mousePressEvent(self, event):
        # Ignorar clics del ratón
        event.ignore()

    def mouseMoveEvent(self, event):
        # Permitir el movimiento del ratón para el cursor, pero no para interactuar con el gráfico
        super().mouseMoveEvent(event)
        event.ignore()

    def mouseReleaseEvent(self, event):
        # Ignorar la liberación del ratón
        event.ignore()


class DeflickerDialog(QDialog):
    # Señal para actualizar la previsualización desde el hilo
    preview_ready = Signal(int, QPixmap)

    def __init__(self, brightness_curve, image_sequence, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de Deflicker Avanzado")
        self.setMinimumSize(1400, 900)

        self.original_curve = brightness_curve
        self.image_sequence = image_sequence
        self.smoothed_curve = None
        self.smoothing_level = 10
        self.smoothing_method = "moving_average"
        self.manual_adjustment = False
        self.control_points = []
        self.current_preview_frame = 0
        self.config_file = "deflicker_settings.json"

        # Para caché y procesamiento en hilos
        self.preview_cache = {}
        self.max_cache_size = 10
        self.preview_thread = None
        self.current_preview_request = None
        self.stop_preview_thread = False

        self.init_ui()
        self.update_plot()
        self.load_settings()

        # Conectar señal
        self.preview_ready.connect(self.on_preview_ready)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Información estadística
        stats_group = QGroupBox("Estadísticas de Brillo")
        stats_layout = QHBoxLayout(stats_group)
        self.stats_label = QLabel("")
        stats_layout.addWidget(self.stats_label)
        main_layout.addWidget(stats_group)

        # Splitter para dividir la interfaz
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Panel izquierdo: Gráfico
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        splitter.addWidget(left_widget)

        # Gráfico personalizado de solo lectura
        self.plot_widget = ReadOnlyPlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle("Curva de Brillo - Análisis de Deflicker", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Brillo (0-255)', color='k')
        self.plot_widget.setLabel('bottom', 'Fotograma', color='k')
        self.plot_widget.showGrid(x=True, y=True)

        # Configuración del ViewBox para deshabilitar interacciones
        view_box = self.plot_widget.getPlotItem().getViewBox()
        view_box.setMouseEnabled(x=False, y=False)
        view_box.setMenuEnabled(False)
        view_box.enableAutoRange(enable=False)

        # Establecer rangos fijos
        if self.original_curve:
            y_min = min(self.original_curve)
            y_max = max(self.original_curve)
            y_margin = (y_max - y_min) * 0.1
            view_box.setYRange(y_min - y_margin, y_max + y_margin)
        view_box.setXRange(0, len(self.original_curve) - 1)

        left_layout.addWidget(self.plot_widget, 1)

        # Leyenda
        self.plot_widget.addLegend()

        # Curvas
        self.original_curve_item = self.plot_widget.plot(
            pen=pg.mkPen('b', width=2),
            name="Original",
            symbol='o',
            symbolSize=3,
            symbolBrush='b'
        )
        self.smoothed_curve_item = self.plot_widget.plot(
            pen=pg.mkPen('r', width=3),
            name="Suavizada",
            symbol='x',
            symbolSize=4,
            symbolBrush='r'
        )

        # Línea vertical para seguimiento del cursor
        self.cursor_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen('g', width=1, style=Qt.DashLine)
        )
        self.cursor_line.setCursor(Qt.ArrowCursor)  # Cursor normal en lugar de mano
        self.plot_widget.addItem(self.cursor_line)

        # Texto para mostrar valores
        self.value_text = pg.TextItem("", anchor=(0, 1), color='k')
        self.plot_widget.addItem(self.value_text)

        # Conectar eventos de mouse
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)

        # Controles
        controls_group = QGroupBox("Controles de Suavizado")
        controls_layout = QVBoxLayout(controls_group)

        # Método de suavizado
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Método:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Media Móvil", "Gaussiano", "Savitzky-Golay", "Wavelet", "Loess"])
        self.method_combo.currentTextChanged.connect(self.on_method_changed)
        method_layout.addWidget(self.method_combo)
        controls_layout.addLayout(method_layout)

        # Slider principal
        slider_layout = QHBoxLayout()
        self.slider_label = QLabel(f"Fuerza de Suavizado: {self.smoothing_level}%")
        slider_layout.addWidget(self.slider_label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(self.smoothing_level)
        self.slider.valueChanged.connect(self.on_slider_change)
        slider_layout.addWidget(self.slider)
        controls_layout.addLayout(slider_layout)

        # Parámetros específicos del método
        self.param_widget = QWidget()
        self.param_layout = QHBoxLayout(self.param_widget)
        self.param_layout.addWidget(QLabel("Ventana:"))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(3, 101)
        self.window_spin.setValue(21)
        self.window_spin.setSingleStep(2)
        self.window_spin.valueChanged.connect(self.on_params_changed)
        self.param_layout.addWidget(self.window_spin)
        self.param_layout.addWidget(QLabel("Sigma:"))
        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.1, 10.0)
        self.sigma_spin.setValue(2.0)
        self.sigma_spin.setSingleStep(0.1)
        self.sigma_spin.valueChanged.connect(self.on_params_changed)
        self.param_layout.addWidget(self.sigma_spin)
        self.param_layout.addWidget(QLabel("Orden:"))
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 5)
        self.order_spin.setValue(3)
        self.order_spin.valueChanged.connect(self.on_params_changed)
        self.param_layout.addWidget(self.order_spin)
        controls_layout.addWidget(self.param_widget)

        # Checkbox para ajuste manual
        self.manual_check = QCheckBox("Ajuste manual")
        self.manual_check.toggled.connect(self.on_manual_toggled)
        controls_layout.addWidget(self.manual_check)

        left_layout.addWidget(controls_group)

        # Panel derecho: Previsualización e histograma
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        splitter.addWidget(right_widget)

        # Previsualización
        preview_group = QGroupBox("Previsualización")
        preview_layout = QVBoxLayout(preview_group)

        # Frame selector
        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("Frame:"))
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, len(self.original_curve) - 1)
        self.frame_spin.valueChanged.connect(self.on_frame_changed)
        frame_layout.addWidget(self.frame_spin)

        self.preview_btn = QPushButton("Actualizar")
        self.preview_btn.clicked.connect(self.update_preview)
        frame_layout.addWidget(self.preview_btn)
        preview_layout.addLayout(frame_layout)

        # Image preview
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("border: 1px solid gray;")
        preview_layout.addWidget(self.preview_label)

        # Info
        self.preview_info = QLabel("Selecciona un frame para previsualizar")
        preview_layout.addWidget(self.preview_info)

        right_layout.addWidget(preview_group)

        # Histograma
        histogram_group = QGroupBox("Histograma de Brillo")
        histogram_layout = QVBoxLayout(histogram_group)
        self.histogram_widget = pg.PlotWidget()
        self.histogram_widget.setBackground('w')
        self.histogram_widget.setTitle("Distribución de Brillo", color="k", size="10pt")
        self.histogram_widget.setLabel('left', 'Frecuencia', color='k')
        self.histogram_widget.setLabel('bottom', 'Brillo', color='k')
        self.histogram_widget.showGrid(x=True, y=True)
        histogram_layout.addWidget(self.histogram_widget)
        right_layout.addWidget(histogram_group)

        # Botones
        button_layout = QHBoxLayout()

        # Botones de guardar/cargar configuración
        self.btn_save = QPushButton("Guardar Config")
        self.btn_save.clicked.connect(self.save_settings)
        button_layout.addWidget(self.btn_save)

        self.btn_load = QPushButton("Cargar Config")
        self.btn_load.clicked.connect(self.load_settings_dialog)
        button_layout.addWidget(self.btn_load)

        # Botón para ver estadísticas avanzadas
        self.btn_stats = QPushButton("Estadísticas Avanzadas")
        self.btn_stats.clicked.connect(self.show_advanced_stats)
        button_layout.addWidget(self.btn_stats)

        button_layout.addStretch()
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_apply)
        button_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(button_layout)

        # Inicializar
        self.on_method_changed(self.method_combo.currentText())
        self.update_stats()
        self.update_histogram()

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()

            # Mover línea vertical al cursor
            self.cursor_line.setPos(x)

            # Mostrar valores en la posición del cursor
            if 0 <= x < len(self.original_curve):
                frame_idx = int(x)
                original_val = self.original_curve[frame_idx]

                # Verificar si smoothed_curve tiene datos
                if self.smoothed_curve is not None and len(self.smoothed_curve) > frame_idx:
                    smoothed_val = self.smoothed_curve[frame_idx]
                else:
                    smoothed_val = original_val

                diff = smoothed_val - original_val
                diff_percent = (diff / original_val * 100) if original_val > 0 else 0

                self.value_text.setText(
                    f"Frame: {frame_idx}\n"
                    f"Original: {original_val:.1f}\n"
                    f"Suavizado: {smoothed_val:.1f}\n"
                    f"Ajuste: {diff:+.1f} ({diff_percent:+.1f}%)"
                )
                self.value_text.setPos(x, y)

    def on_method_changed(self, method_text):
        method_map = {
            "Media Móvil": "moving_average",
            "Gaussiano": "gaussian",
            "Savitzky-Golay": "savitzky_golay",
            "Wavelet": "wavelet",
            "Loess": "loess"
        }
        self.smoothing_method = method_map[method_text]

        # Mostrar/ocultar parámetros según el método
        if self.smoothing_method == "gaussian":
            self.window_spin.setVisible(True)
            self.sigma_spin.setVisible(True)
            self.order_spin.setVisible(False)
        elif self.smoothing_method == "savitzky_golay":
            self.window_spin.setVisible(True)
            self.sigma_spin.setVisible(False)
            self.order_spin.setVisible(True)
        elif self.smoothing_method == "wavelet":
            self.window_spin.setVisible(False)
            self.sigma_spin.setVisible(True)
            self.order_spin.setVisible(False)
        elif self.smoothing_method == "loess":
            self.window_spin.setVisible(True)
            self.sigma_spin.setVisible(False)
            self.order_spin.setVisible(False)
        else:  # moving_average
            self.window_spin.setVisible(True)
            self.sigma_spin.setVisible(False)
            self.order_spin.setVisible(False)

        self.update_plot()

    def on_params_changed(self):
        self.update_plot()

    def on_manual_toggled(self, checked):
        self.manual_adjustment = checked
        if checked:
            # Habilitar la edición de la curva
            self.plot_widget.setMouseEnabled(x=True, y=True)
            # Conectar eventos para agregar puntos de control
            self.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)
            # Inicializar con la curva suavizada actual
            if self.smoothed_curve is not None:
                self.control_points = [(i, val) for i, val in enumerate(self.smoothed_curve)]
        else:
            self.plot_widget.setMouseEnabled(x=True, y=False)
            try:
                self.plot_widget.scene().sigMouseClicked.disconnect(self.on_plot_clicked)
            except:
                pass
            self.control_points = []
            self.update_plot()

    def on_plot_clicked(self, event):
        if event.button() == Qt.LeftButton and self.manual_adjustment:
            pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
            x, y = pos.x(), pos.y()
            if 0 <= x < len(self.original_curve):
                # Agregar punto de control
                self.control_points.append((int(x), y))
                # Ordenar por frame
                self.control_points.sort(key=lambda p: p[0])
                self.update_manual_curve()

    def update_manual_curve(self):
        if not self.control_points:
            return

        # Crear curva manual interpolando puntos de control
        frames = [p[0] for p in self.control_points]
        values = [p[1] for p in self.control_points]
        x_new = np.arange(len(self.original_curve))

        # Interpolación cúbica para una curva suave
        from scipy import interpolate
        if len(frames) > 3:
            tck = interpolate.splrep(frames, values, s=0)
            y_new = interpolate.splev(x_new, tck, der=0)
        else:
            # Interpolación lineal si no hay suficientes puntos
            y_new = np.interp(x_new, frames, values)

        self.smoothed_curve = y_new.tolist() if hasattr(y_new, 'tolist') else []
        x_data = list(range(len(self.original_curve)))

        # Solo establecer datos si smoothed_curve tiene la longitud correcta
        if self.smoothed_curve is not None and len(self.smoothed_curve) == len(self.original_curve):
            self.smoothed_curve_item.setData(x_data, self.smoothed_curve)
        else:
            self.smoothed_curve_item.setData([], [])

        # Actualizar estadísticas e histograma
        self.update_stats()
        self.update_histogram()

    def on_frame_changed(self, frame_idx):
        self.current_preview_frame = frame_idx
        self.update_preview()

    def update_preview(self):
        # Verificar que image_sequence sea una lista con elementos
        if (not isinstance(self.image_sequence, list) or
                not self.image_sequence or
                self.current_preview_frame >= len(self.image_sequence)):
            return

        frame_idx = self.current_preview_frame
        image_path = self.image_sequence[frame_idx]

        # Verificar si ya tenemos esta previsualización en cache
        if image_path in self.preview_cache:
            pixmap = self.preview_cache[image_path]
            self.preview_label.setPixmap(pixmap)
            self.update_preview_info(frame_idx)
            return

        # Establecer bandera para detener cualquier hilo anterior
        self.stop_preview_thread = True

        # Pequeña pausa para permitir que el hilo anterior detecte la bandera
        if self.preview_thread and self.preview_thread.is_alive():
            time.sleep(0.1)

        # Reiniciar bandera
        self.stop_preview_thread = False

        # Actualizar la solicitud actual
        self.current_preview_request = frame_idx

        # Mostrar mensaje de carga
        self.preview_label.setText("Cargando...")

        # Iniciar nuevo hilo
        self.preview_thread = threading.Thread(
            target=self._generate_preview_thread,
            args=(frame_idx, image_path),
            daemon=True
        )
        self.preview_thread.start()

    def _generate_preview_thread(self, frame_idx, image_path):
        """Genera la previsualización en un hilo separado"""
        try:
            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            # Verificar si es un archivo RAW
            raw_extensions = ['.raw', '.cr2', '.nef', '.arw', '.raf']
            if any(image_path.lower().endswith(ext) for ext in raw_extensions):
                # Verificar si debemos detener este hilo
                if self.stop_preview_thread:
                    return

                # Usar rawpy para archivos RAW con ajustes optimizados
                with rawpy.imread(image_path) as raw:
                    # Verificar si debemos detener este hilo
                    if self.stop_preview_thread:
                        return

                    # Parámetros compatibles con la API de rawpy
                    rgb = raw.postprocess(
                        use_camera_wb=True,
                        use_auto_wb=False,
                        no_auto_bright=False,
                        output_color=rawpy.ColorSpace.sRGB,
                        gamma=(2.2, 4.2),
                        output_bps=8,
                        half_size=True,
                        no_auto_scale=False
                    )

                    # Verificar si debemos detener este hilo
                    if self.stop_preview_thread:
                        return

                    image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            else:
                # Verificar si debemos detener este hilo
                if self.stop_preview_thread:
                    return

                # Usar OpenCV para otros formatos
                image = cv2.imread(image_path)

            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            if image is None:
                print(f"No se pudo cargar la imagen: {image_path}")
                return

            # Aplicar corrección de brillo si hay curva suavizada
            if (self.smoothed_curve is not None and
                    len(self.smoothed_curve) > frame_idx):

                # Verificar si debemos detener este hilo
                if self.stop_preview_thread:
                    return

                original_brightness = self.original_curve[frame_idx]
                target_brightness = self.smoothed_curve[frame_idx]

                if original_brightness > 0:
                    correction_factor = target_brightness / original_brightness
                else:
                    correction_factor = 1.0

                # Aplicar corrección con ajuste de gamma
                image = self.apply_brightness_correction(image, correction_factor)

            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            # Aplicar un ajuste de brillo general
            image = self.apply_general_brightness_adjustment(image, 1.2)

            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            # Convertir a QImage
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w, ch = image_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            else:
                h, w = image.shape
                bytes_per_line = w
                qt_image = QImage(image.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            # Convertir a QPixmap
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Verificar si debemos detener este hilo
            if self.stop_preview_thread:
                return

            # Emitir señal para actualizar la UI
            self.preview_ready.emit(frame_idx, scaled_pixmap)

        except Exception as e:
            print(f"Error al generar previsualización: {e}")

    def apply_brightness_correction(self, image, correction_factor):
        """Aplica corrección de brillo con ajuste de gamma"""
        # Convertir a float para operaciones
        img_float = image.astype(np.float32) / 255.0

        # Aplicar corrección con curva gamma
        gamma = 1.0 / max(0.1, min(2.0, correction_factor))
        img_corrected = np.power(img_float, gamma)

        # Volver a 8-bit
        return (img_corrected * 255).astype(np.uint8)

    def apply_general_brightness_adjustment(self, image, factor):
        """Aplica un ajuste general de brillo a la imagen"""
        # Convertir a float para operaciones
        img_float = image.astype(np.float32)

        # Aplicar factor de brillo
        img_adjusted = img_float * factor

        # Asegurar que los valores estén en el rango correcto
        img_adjusted = np.clip(img_adjusted, 0, 255)

        # Volver a 8-bit
        return img_adjusted.astype(np.uint8)

    def on_preview_ready(self, frame_idx, pixmap):
        """Maneja la previsualización lista desde el hilo"""
        if frame_idx != self.current_preview_frame:
            return  # Esta previsualización ya no es relevante

        self.preview_label.setPixmap(pixmap)
        self.update_preview_info(frame_idx)

        # Guardar en cache
        image_path = self.image_sequence[frame_idx]
        self.preview_cache[image_path] = pixmap

        # Limitar el tamaño del cache
        if len(self.preview_cache) > self.max_cache_size:
            oldest_key = next(iter(self.preview_cache))
            del self.preview_cache[oldest_key]

    def update_preview_info(self, frame_idx):
        """Actualiza la información de previsualización"""
        if 0 <= frame_idx < len(self.original_curve):
            original_val = self.original_curve[frame_idx]

            if self.smoothed_curve is not None and len(self.smoothed_curve) > frame_idx:
                smoothed_val = self.smoothed_curve[frame_idx]
            else:
                smoothed_val = original_val

            diff = smoothed_val - original_val
            diff_percent = (diff / original_val * 100) if original_val > 0 else 0

            self.preview_info.setText(
                f"Frame: {frame_idx}\n"
                f"Brillo original: {original_val:.1f}\n"
                f"Brillo suavizado: {smoothed_val:.1f}\n"
                f"Ajuste: {diff:+.1f} ({diff_percent:+.1f}%)"
            )

    def on_slider_change(self, value):
        self.smoothing_level = value
        self.slider_label.setText(f"Fuerza de Suavizado: {value}%")
        self.update_plot()

    def update_plot(self):
        if self.manual_adjustment:
            return

        # Calcular parámetros de suavizado
        window_size = self.window_spin.value()
        sigma = self.sigma_spin.value()
        order = self.order_spin.value()

        # Suavizar datos según el método seleccionado
        if self.smoothing_method == "moving_average":
            smoothed = self.moving_average_smooth(self.original_curve, window_size)
        elif self.smoothing_method == "gaussian":
            smoothed = self.gaussian_smooth(self.original_curve, window_size, sigma)
        elif self.smoothing_method == "savitzky_golay":
            smoothed = self.savitzky_golay_smooth(self.original_curve, window_size, order)
        elif self.smoothing_method == "wavelet":
            smoothed = self.wavelet_smooth(self.original_curve, sigma)
        elif self.smoothing_method == "loess":
            smoothed = self.loess_smooth(self.original_curve, window_size)
        else:
            smoothed = self.original_curve

        self.smoothed_curve = smoothed

        # Actualizar gráfico
        x_data = list(range(len(self.original_curve)))
        self.original_curve_item.setData(x_data, self.original_curve)

        # Solo establecer datos si smoothed_curve tiene la longitud correcta
        if self.smoothed_curve is not None and len(self.smoothed_curve) == len(self.original_curve):
            self.smoothed_curve_item.setData(x_data, self.smoothed_curve)
        else:
            self.smoothed_curve_item.setData([], [])

        # Actualizar histograma
        self.update_histogram()

        # Actualizar estadísticas
        self.update_stats()

    def update_histogram(self):
        self.histogram_widget.clear()

        if not self.original_curve:
            return

        # Histograma de la curva original
        y1, x1 = np.histogram(self.original_curve, bins=50, range=(0, 255))
        # Para stepMode=True, necesitamos que X tenga longitud len(Y)+1
        self.histogram_widget.plot(x1, y1, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150), pen='b', name="Original")

        # Histograma de la curva suavizada
        if self.smoothed_curve is not None and len(self.smoothed_curve) > 0:
            y2, x2 = np.histogram(self.smoothed_curve, bins=50, range=(0, 255))
            self.histogram_widget.plot(x2, y2, stepMode=True, fillLevel=0, brush=(255, 0, 0, 150), pen='r',
                                       name="Suavizada")

        self.histogram_widget.addLegend()

    def update_stats(self):
        if not self.original_curve:
            return

        # Calcular estadísticas
        original_mean = np.mean(self.original_curve)
        original_std = np.std(self.original_curve)
        original_var = np.var(self.original_curve)

        if self.smoothed_curve is not None and len(self.smoothed_curve) > 0:
            smoothed_mean = np.mean(self.smoothed_curve)
            smoothed_std = np.std(self.smoothed_curve)
            smoothed_var = np.var(self.smoothed_curve)

            reduction_std = (original_std - smoothed_std) / original_std * 100
            reduction_var = (original_var - smoothed_var) / original_var * 100

            stats_text = (
                f"Original: μ={original_mean:.1f}, σ={original_std:.1f}, σ²={original_var:.1f} | "
                f"Suavizado: μ={smoothed_mean:.1f}, σ={smoothed_std:.1f} | "
                f"Reducción: σ={reduction_std:.1f}%, σ²={reduction_var:.1f}%"
            )
        else:
            stats_text = f"Brillo: μ={original_mean:.1f}, σ={original_std:.1f}, σ²={original_var:.1f}"

        self.stats_label.setText(stats_text)

    def moving_average_smooth(self, data, window_size):
        """Suavizado por media móvil con manejo de bordes"""
        if window_size % 2 == 0:
            window_size += 1

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
        except ImportError:
            print("Advertencia: pywt no instalado. Usando media móvil.")
            return self.moving_average_smooth(data, 21)

    def loess_smooth(self, data, window_size):
        """Suavizado LOESS (regresión local)"""
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            x = np.arange(len(data))
            frac = window_size / len(data)
            smoothed = lowess(data, x, frac=frac, it=0, return_sorted=False)
            return smoothed
        except ImportError:
            print("Advertencia: statsmodels no instalado. Usando media móvil.")
            return self.moving_average_smooth(data, window_size)

    def show_advanced_stats(self):
        """Mostrar diálogo con estadísticas avanzadas"""
        from PySide6.QtWidgets import QMessageBox

        if not self.original_curve:
            return

        stats_text = self.calculate_advanced_stats()

        msg = QMessageBox(self)
        msg.setWindowTitle("Estadísticas Avanzadas de Brillo")
        msg.setText(stats_text)
        msg.exec()

    def calculate_advanced_stats(self):
        """Calcular estadísticas avanzadas de la curva de brillo"""
        original = np.array(self.original_curve)

        # Verificar si smoothed_curve tiene datos
        if self.smoothed_curve is not None and len(self.smoothed_curve) > 0:
            smoothed = np.array(self.smoothed_curve)
        else:
            smoothed = original

        stats = [
            "=== ESTADÍSTICAS AVANZADAS ===",
            f"Fotogramas analizados: {len(original)}",
            "",
            "--- CURVA ORIGINAL ---",
            f"Media (μ): {np.mean(original):.2f}",
            f"Desviación estándar (σ): {np.std(original):.2f}",
            f"Varianza (σ²): {np.var(original):.2f}",
            f"Mínimo: {np.min(original):.2f}",
            f"Máximo: {np.max(original):.2f}",
            f"Rango: {np.ptp(original):.2f}",
            f"Asimetría: {self.calculate_skewness(original):.3f}",
            f"Curtosis: {self.calculate_kurtosis(original):.3f}",
            "",
            "--- CURVA SUAVIZADA ---",
            f"Media (μ): {np.mean(smoothed):.2f}",
            f"Desviación estándar (σ): {np.std(smoothed):.2f}",
            f"Varianza (σ²): {np.var(smoothed):.2f}",
            f"Mínimo: {np.min(smoothed):.2f}",
            f"Máximo: {np.max(smoothed):.2f}",
            f"Rango: {np.ptp(smoothed):.2f}",
            f"Asimetría: {self.calculate_skewness(smoothed):.3f}",
            f"Curtosis: {self.calculate_kurtosis(smoothed):.3f}",
            "",
            "--- MEJORA ESTADÍSTICA ---",
            f"Reducción de desviación estándar: {((np.std(original) - np.std(smoothed)) / np.std(original) * 100):.1f}%",
            f"Reducción de varianza: {((np.var(original) - np.var(smoothed)) / np.var(original) * 100):.1f}%",
            f"Diferencia de medias: {(np.mean(smoothed) - np.mean(original)):.3f}",
        ]

        return "\n".join(stats)

    def calculate_skewness(self, data):
        """Calcular asimetría de los datos"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 3)

    def calculate_kurtosis(self, data):
        """Calcular curtosis de los datos"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 4) - 3

    def save_settings(self):
        """Guardar configuración actual a archivo"""
        settings = {
            "smoothing_method": self.smoothing_method,
            "smoothing_level": self.smoothing_level,
            "window_size": self.window_spin.value(),
            "sigma": self.sigma_spin.value(),
            "order": self.order_spin.value(),
            "manual_adjustment": self.manual_adjustment,
            "control_points": self.control_points
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f)
            QMessageBox.information(self, "Configuración Guardada", "La configuración se ha guardado correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la configuración: {str(e)}")

    def load_settings(self):
        """Cargar configuración desde archivo (si existe)"""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, 'r') as f:
                settings = json.load(f)

            # Aplicar configuración
            method_map_reverse = {v: k for k, v in {
                "Media Móvil": "moving_average",
                "Gaussiano": "gaussian",
                "Savitzky-Golay": "savitzky_golay",
                "Wavelet": "wavelet",
                "Loess": "loess"
            }.items()}

            if settings["smoothing_method"] in method_map_reverse:
                self.method_combo.setCurrentText(method_map_reverse[settings["smoothing_method"]])

            self.slider.setValue(settings.get("smoothing_level", 10))
            self.window_spin.setValue(settings.get("window_size", 21))
            self.sigma_spin.setValue(settings.get("sigma", 2.0))
            self.order_spin.setValue(settings.get("order", 3))
            self.manual_check.setChecked(settings.get("manual_adjustment", False))
            self.control_points = settings.get("control_points", [])

            if self.manual_adjustment and self.control_points:
                self.update_manual_curve()
            else:
                self.update_plot()

        except Exception as e:
            print(f"Error al cargar configuración: {str(e)}")

    def load_settings_dialog(self):
        """Cargar configuración desde diálogo de archivo"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Configuración", "", "JSON Files (*.json)"
        )

        if file_path:
            self.config_file = file_path
            self.load_settings()

    def get_smoothing_level(self):
        return self.smoothing_level

    def get_smoothed_curve(self):
        return self.smoothed_curve

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Redimensionar la previsualización cuando cambie el tamaño del diálogo
        self.update_preview_scaling()

    def update_preview_scaling(self):
        """Actualiza el escalado de la previsualización"""
        # Si hay una imagen en cache para el frame actual, reescalarla
        if self.current_preview_frame < len(self.image_sequence):
            image_path = self.image_sequence[self.current_preview_frame]
            if image_path in self.preview_cache:
                pixmap = self.preview_cache[image_path]
                scaled_pixmap = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)