import PyInstaller.__main__
import os

PyInstaller.__main__.run([
    'app/main.py',
    '--name=TimelapseCreator',
    '--windowed',
    '--onefile',
    '--icon=app/ui/resources/icons/app_icon.ico',
    '--add-data=app/ui/resources;app/ui/resources',
    '--hidden-import=rawpy',
    '--hidden-import=numpy',
])
