# app/core/export_thread.py
from PySide6.QtCore import QThread, Signal
from .video_exporter import VideoExporter


class ExportThread(QThread):
    progress = Signal(int)
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, image_sequence, output_path, fps, resolution, codec):
        super().__init__()
        self.image_sequence = image_sequence
        self.output_path = output_path
        self.fps = fps
        self.resolution = resolution
        self.codec = codec
        self.exporter = VideoExporter()
        self.exporter.progress_updated.connect(self.handle_progress)

    def handle_progress(self, value):
        self.progress.emit(value)

    def run(self):
        try:
            success = self.exporter.export_video(
                self.image_sequence,
                self.output_path,
                self.fps,
                self.resolution,
                self.codec
            )
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)