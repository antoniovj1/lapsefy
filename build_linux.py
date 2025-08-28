import os
import subprocess

# Primero instalar PyInstaller si no está instalado
# pip install pyinstaller

# Construir con PyInstaller
subprocess.run([
    'pyinstaller',
    'app/main.py',
    '--name=TimelapseCreator',
    '--windowed',
    '--onefile',
    '--icon=app/ui/resources/icons/app_icon.png',
    '--add-data=app/ui/resources:app/ui/resources',
    '--hidden-import=rawpy',
    '--hidden-import=numpy',
])

# Luego usar linuxdeployqt para crear AppImage
# Descargar linuxdeployqt desde https://github.com/probonopd/linuxdeployqt
# y seguir las instrucciones para crear el AppImage
