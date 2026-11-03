@echo off
cd /d "%~dp0"
docker compose -f compose.listing.yaml up -d --build
if errorlevel 1 (
  echo Open Docker Desktop and try again.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8081/listing-tool/
