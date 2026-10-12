@echo off
cd /d "%~dp0"
taskkill /F /IM LlamaRunner.exe >nul 2>&1
rmdir /s /q build dist 2>nul
py -m pip install --upgrade pyinstaller
py -m PyInstaller --clean --onefile --noconsole --hidden-import bench_panel --hidden-import server_panel --name LlamaRunner launcher.py
if errorlevel 1 goto :fail
if exist models.ini copy /y models.ini dist\models.ini
if exist settings.ini copy /y settings.ini dist\settings.ini
if exist mcp.json copy /y mcp.json dist\mcp.json
echo.
echo Output: dist\LlamaRunner.exe  (title bar must say "llama-server runner v9")
pause
exit /b 0
:fail
echo BUILD FAILED
pause
exit /b 1
