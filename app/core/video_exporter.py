# app/core/video_exporter.py (modificaciones)
import cv2
import subprocess
import os
import tempfile
import shutil
import numpy as np


class VideoExporter:
    def __init__(self):
        pass

    def export_video(self, image_sequence, output_path, fps=30, resolution="1920x1080", codec='libx264'):
        """Exporta una secuencia de imágenes (arrays numpy) a video usando FFmpeg"""
        if not image_sequence:
            print("Secuencia de imágenes vacía")
            return False

        # Parsear resolución
        width, height = map(int, resolution.split('x'))

        # Determinar codec y opciones basado en la elección
        codec_options = {
            'libx264': {
                'codec': 'libx264',
                'pix_fmt': 'yuv420p',
                'crf': '23'
            },
            'libx265': {
                'codec': 'libx265',
                'pix_fmt': 'yuv420p',
                'crf': '28'
            },
            'mpeg4': {
                'codec': 'mpeg4',
                'pix_fmt': 'yuv420p',
                'qscale': '5'
            },
            'prores': {
                'codec': 'prores_ks',
                'pix_fmt': 'yuv422p10le',
                'profile': '3'
            }
        }

        if codec not in codec_options:
            codec = 'libx264'

        options = codec_options[codec]

        temp_dir = None
        try:
            # Guardar imágenes en archivos temporales (FFmpeg necesita archivos)
            temp_dir = tempfile.mkdtemp()
            file_list = []

            for i, img in enumerate(image_sequence):
                filename = os.path.join(temp_dir, f"frame_{i:06d}.jpg")
                success = cv2.imwrite(filename, img)
                if success:
                    file_list.append(filename)
                else:
                    print(f"Error al guardar frame {i}")

            # Crear archivo temporal con lista de imágenes
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for image_path in file_list:
                    f.write(f"file '{os.path.abspath(image_path)}'\n")
                list_file = f.name

            # Construir comando FFmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Sobrescribir archivo existente
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-r', str(fps),
                '-s', resolution,
                '-c:v', options['codec'],
                '-pix_fmt', options['pix_fmt'],
            ]

            # Añadir opciones de calidad según el codec
            if options.get('crf'):
                cmd.extend(['-crf', options['crf']])
            elif options.get('qscale'):
                cmd.extend(['-qscale:v', options['qscale']])
            elif options.get('profile'):
                cmd.extend(['-profile:v', options['profile']])

            cmd.append(output_path)

            # Ejecutar FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Limpiar archivos temporales
            os.unlink(list_file)
            if temp_dir:
                shutil.rmtree(temp_dir)

            if result.returncode == 0:
                return True
            else:
                print(f"Error en FFmpeg: {result.stderr}")
                return False

        except Exception as e:
            print(f"Error al exportar video: {e}")
            if temp_dir:
                shutil.rmtree(temp_dir)
            return False