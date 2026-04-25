@echo off
setlocal
title YouTube-Storage Setup
cd %~dp0
  python -m venv runtime
  call runtime\Scripts\activate
REM Update PIP (if need only):
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  del get-pip.py
  python -m pip install --upgrade pip
  pip install -r requirements.txt
echo.
echo YouTube-Storage has been installed successfully...
pause