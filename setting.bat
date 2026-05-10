@echo off
set ENV_NAME=AI-OCC_Study

where conda >nul 2>nul
if errorlevel 1 (
    echo [ERROR] conda command not found.
    echo Please install Anaconda or Miniconda first.
    pause
    exit /b 1
)

call conda create -n %ENV_NAME% python=3.10 -y
call conda activate %ENV_NAME%

python -m pip install --upgrade pip
call conda install -c conda-forge pythonocc-core=7.7.2 pyqt=6 -y
python -m pip install -r requirments.txt

huggingface-cli login
