@echo off
echo === Building DBTesterToolkit.exe ===
python -m pip install -r requirements.txt || goto :err
python -m PyInstaller --noconfirm --onefile --name DBTesterToolkit --add-data "templates;templates" --hidden-import oracledb --hidden-import pyodbc --hidden-import pymysql app.py || goto :err
echo.
echo Done! Your exe is in the "dist" folder: dist\DBTesterToolkit.exe
pause & exit /b
:err
echo Build failed. Make sure Python 3.9+ is installed and on PATH.
pause
