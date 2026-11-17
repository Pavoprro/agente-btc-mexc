@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
title Agente BTC/USDT - MEXC Paper

echo.
echo  ===== Agente BTC/USDT =====
echo.

where python >nul 2>nul || (echo  Falta Python. Instala Python 3.11 o mas nuevo y vuelve a correr esto. & pause & exit /b 1)
where npm >nul 2>nul || (echo  Falta Node.js. Instala Node 20 o mas nuevo y vuelve a correr esto. & pause & exit /b 1)

if not exist backend\.venv\Scripts\python.exe (
  echo  [1/4] Preparando el entorno de Python ^(solo la primera vez^)...
  python -m venv backend\.venv || (pause & exit /b 1)
  backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || (pause & exit /b 1)
) else (
  echo  [1/4] Entorno de Python listo.
)

if not exist backend\modelo\v1\modelo.json (
  echo        Exportando el modelo v1...
  pushd backend
  .venv\Scripts\python modelo\exportar.py || (popd & pause & exit /b 1)
  popd
)

if not exist backend\.env (
  echo  [2/4] Creando backend\.env con una clave nueva...
  backend\.venv\Scripts\python -c "import secrets; open('backend/.env','w',encoding='utf-8').write('# Generado por arrancar.bat. Este archivo NO se sube al repo.\nAPI_KEY=' + secrets.token_urlsafe(24) + '\n')" || (pause & exit /b 1)
) else (
  echo  [2/4] backend\.env ya existe.
)
for /f "tokens=1,* delims==" %%a in ('findstr /b "API_KEY=" backend\.env') do set CLAVE=%%b

if not exist frontend\node_modules (
  echo  [3/4] Instalando el panel ^(npm install, solo la primera vez^)...
  pushd frontend
  call npm install --silent || (popd & pause & exit /b 1)
  popd
) else (
  echo  [3/4] Panel instalado.
)
echo        Compilando el panel...
pushd frontend
call npm run build --silent >nul || (popd & echo  Fallo al compilar el panel. & pause & exit /b 1)
popd

echo  [4/4] Backend en http://localhost:8765 ^(API en /api, docs en /docs^)
echo.
echo  Clave de la API: %CLAVE%
echo  El navegador se abre ya con la clave puesta. Cierra esta ventana para apagar el agente.
echo.
if not defined AGENTE_SIN_NAVEGADOR start "" "http://localhost:8765/#clave=%CLAVE%"
pushd backend
.venv\Scripts\python -m uvicorn app.main:crear_app --factory --port 8765 --log-level warning
popd
pause
