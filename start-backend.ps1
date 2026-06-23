Set-Location $PSScriptRoot\backend

if (-not (Test-Path "venv\Scripts\python.exe")) {
    py -m venv venv
}

& .\venv\Scripts\python.exe -m pip install -r requirements.txt -q
& .\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
