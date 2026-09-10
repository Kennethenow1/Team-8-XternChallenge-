@echo off
REM Run project Python inside Ubuntu WSL2 with CUDA.
wsl -d Ubuntu -e /home/magjun/venvs/team8-miso/bin/python %*
