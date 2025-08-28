@echo off
REM install_windows.bat

echo Instalando dependencias de Python...
python -m venv venv

echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt

echo.
echo Instalación completada.
echo Para ejecutar la aplicación:
echo venv\Scripts\activate.bat
echo python -m app.main
echo.
pause