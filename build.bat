@echo off
cd /d "%~dp0"
taskkill /F /IM LlamaRunner.exe >nul 2>&1
rmdir /s /q build dist 2>nul
py -m pip install --upgrade pyinstaller
py -m PyInstaller --clean --onefile --noconsole --hidden-import bench_panel --hidden-import server_panel --name LlamaRunner launcher.py
mkdir dist\config
mkdir dist\llama-server
if errorlevel 1 goto :fail
if exist config xcopy /e /i /y config dist\config
if exist llama-server xcopy /e /i /y llama-server dist\llama-server
echo.
echo Output: dist\LlamaRunner.exe  (title bar must say "llama-server runner v9")
pause
exit /b 0
:fail
echo BUILD FAILED
pause
exit /b 1
