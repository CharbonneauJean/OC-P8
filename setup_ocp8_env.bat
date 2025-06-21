@echo off
setlocal enabledelayedexpansion

:: ■■ Configuration Parameters ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
set ENV_NAME=ocp8_env
set PY_VERSION=3.10
set PROJECT_DIR=%cd%

:: ■■ Color codes for output ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
:: Note: Windows batch doesn't support colors as easily as bash
echo.
echo ========================================================
echo    OC-P8 Conda Environment Setup for Windows
echo ========================================================
echo.

:: ■■ Check if conda is installed ■■■■■■■■■■■■■■■■■■■■■■■■■
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Conda is not installed or not in PATH.
    echo Please install Miniconda or Anaconda first.
    echo Download from: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo [INFO] Found conda at: 
where conda
echo.

:: ■■ Remove existing environment if it exists ■■■■■■■■■■■■■
echo [INFO] Checking for existing environment...
conda env list | findstr /C:"%ENV_NAME%" >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Environment '%ENV_NAME%' exists. Removing...
    call conda env remove -y -n %ENV_NAME%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to remove existing environment
        pause
        exit /b 1
    )
)

:: ■■ Create new conda environment ■■■■■■■■■■■■■■■■■■■■■■■■
echo.
echo [INFO] Creating conda environment '%ENV_NAME%' with Python %PY_VERSION%...
call conda create -y -n %ENV_NAME% python=%PY_VERSION%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create conda environment
    pause
    exit /b 1
)

:: ■■ Activate environment and install packages ■■■■■■■■■■■■
echo.
echo [INFO] Activating environment and installing packages...
call conda activate %ENV_NAME%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate conda environment
    pause
    exit /b 1
)

:: ■■ Install conda packages ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
echo.
echo [INFO] Installing conda packages...
call conda install -y pandas numpy pillow pyarrow jupyter notebook matplotlib seaborn scikit-learn
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install conda packages
    pause
    exit /b 1
)

:: ■■ Install pip packages ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
echo.
echo [INFO] Installing PySpark...
pip install --no-cache-dir pyspark==3.5.5
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PySpark
    pause
    exit /b 1
)

echo.
echo [INFO] Installing TensorFlow...
pip install --no-cache-dir tensorflow==2.15.0
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install TensorFlow
    pause
    exit /b 1
)

echo.
echo [INFO] Installing additional ML packages...
pip install --no-cache-dir keras-applications keras-preprocessing
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Keras packages
    pause
    exit /b 1
)

echo.
echo [INFO] Installing TensorFlowOnSpark...
pip install --no-cache-dir tensorflowonspark
if %errorlevel% neq 0 (
    echo [WARNING] Failed to install TensorFlowOnSpark (optional package)
)

:: ■■ Clean conda cache ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
echo.
echo [INFO] Cleaning conda cache...
call conda clean -afy

:: ■■ Create activation helper script ■■■■■■■■■■■■■■■■■■■■■
echo.
echo [INFO] Creating activation helper script...
(
echo @echo off
echo call conda activate %ENV_NAME%
echo cd /d "%PROJECT_DIR%"
echo echo.
echo echo Environment '%ENV_NAME%' activated!
echo echo Current directory: %%cd%%
echo echo.
echo echo To start Jupyter Notebook, run:
echo echo    jupyter notebook
echo echo.
) > activate_ocp8.bat

:: ■■ Create Jupyter launcher script ■■■■■■■■■■■■■■■■■■■■■■
(
echo @echo off
echo call conda activate %ENV_NAME%
echo cd /d "%PROJECT_DIR%"
echo jupyter notebook
) > launch_jupyter.bat

:: ■■ Display completion message ■■■■■■■■■■■■■■■■■■■■■■■■■■
echo.
echo ========================================================
echo    Installation completed successfully!
echo ========================================================
echo.
echo Environment name: %ENV_NAME%
echo Python version: %PY_VERSION%
echo Project directory: %PROJECT_DIR%
echo.
echo To work with this environment:
echo.
echo 1) Use the helper script:
echo    activate_ocp8.bat
echo.
echo 2) Or manually activate:
echo    conda activate %ENV_NAME%
echo    cd "%PROJECT_DIR%"
echo.
echo 3) To launch Jupyter directly:
echo    launch_jupyter.bat
echo.
echo ========================================================
echo.
pause
