# app/ui/deflicker_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QSlider, QLabel, QGroupBox)
from PySide6.QtCore import Qt
import pyqtgraph as pg


class DeflickerDialog(QDialog):
    def __init__(self, brightness_curve, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de Deflicker")
        self.setMinimumSize(800, 600)

        self.original_curve = brightness_curve
        self.smoothed_curve = []
        self.smoothing_level = 20  # Valor inicial

        self.init_ui()
        self.update_plot()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Gráfico
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle("Curva de Brillo", color="k", size="12pt")
        self.plot_widget.setLabel('left', 'Brillo', color='k')
        self.plot_widget.setLabel('bottom', 'Fotograma', color='k')
        self.plot_widget.showGrid(x=True, y=True)
        main_layout.addWidget(self.plot_widget)

        # Curvas
        self.original_curve_item = self.plot_widget.plot(pen=pg.mkPen('y', width=2), name="Original")
        self.smoothed_curve_item = self.plot_widget.plot(pen=pg.mkPen('g', width=2), name="Suavizada")

        # Controles
        controls_group = QGroupBox("Controles")
        controls_layout = QHBoxLayout(controls_group)

        self.slider_label = QLabel(f"Nivel de Suavizado: {self.smoothing_level}")
        controls_layout.addWidget(self.slider_label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(self.smoothing_level)
        self.slider.valueChanged.connect(self.on_slider_change)
        controls_layout.addWidget(self.slider)

        main_layout.addWidget(controls_group)

        # Botones
        button_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_apply)
        button_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(button_layout)

    def on_slider_change(self, value):
        self.smoothing_level = value
        self.slider_label.setText(f"Nivel de Suavizado: {self.smoothing_level}")
        self.update_plot()

    def update_plot(self):
        # Esta función se debe conectar a la lógica de suavizado
        # Aquí simulamos una curva suavizada para el ejemplo
        window_size = self.smoothing_level
        if window_size % 2 == 0:
            window_size += 1

        smoothed = self.smooth_data(self.original_curve, window_size)
        self.smoothed_curve = smoothed

        self.original_curve_item.setData(self.original_curve)
        self.smoothed_curve_item.setData(self.smoothed_curve)

    def smooth_data(self, data, window_size):
        """Suaviza datos usando media móvil (convolución)"""
        import numpy as np
        if not data:
            return []

        smoothed = np.convolve(data, np.ones(window_size) / window_size, mode='same')

        # Corregir los bordes
        half_window = window_size // 2
        for i in range(half_window):
            smoothed[i] = np.mean(data[:i + half_window + 1])
            smoothed[-(i + 1)] = np.mean(data[-(i + half_window + 1):])

        return smoothed.tolist()

    def get_smoothing_level(self):
        return self.smoothing_level
