@echo off
setlocal
title YouTube Encrypter Setup
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
echo YouTube Encrypter Setup has been installed successfully...
pause