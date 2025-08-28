#!/bin/bash
# install_linux.sh

echo "Instalando dependencias del sistema..."
sudo apt update
sudo apt install -y ffmpeg python3-pip python3-venv

echo "Creando entorno virtual..."
python3 -m venv venv

echo "Activando entorno virtual..."
source venv/bin/activate

echo "Instalando dependencias de Python..."
pip install -r requirements.txt

echo "Instalación completada."
echo "Para ejecutar la aplicación:"
echo "source venv/bin/activate"
echo "python -m app.main"