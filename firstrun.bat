@echo off
:: Enable delayed expansion for variables inside IF blocks
setlocal enabledelayedexpansion

:: --- CONFIGURATION ---
set "LOGFILE=%~dp0setup_log.txt"
set "DATA_DIR=data"
set "VENV_DIR=venv"
set "KIOSK_DIR=kiosk_app"
set "EXE_NAME=NPRI Viewer.exe"
set "PORT=3500"
set "PYTHON_URL=https://www.python.org/downloads/windows/"
set "REPO_URL=https://github.com/KEIRAN-SN/NPRI-GENERATOR"

:: 1. Initialize Log File (Overwrites old logs)
echo ================================================= > "%LOGFILE%"
echo SETUP STARTED: %date% %time% >> "%LOGFILE%"
echo ================================================= >> "%LOGFILE%"

echo [1/10] CHECKING GIT...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOG] Git not found. Attempting install... >> "%LOGFILE%"
    echo Git not found. Attempting to install via Windows Package Manager...
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements >nul 2>&1
    
    :: Refresh Path
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
    
    git --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo WARNING: winget failed. Downloading standard Git installer...
        curl -L "https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/Git-2.45.0-64-bit.exe" -o git_installer.exe
        start /wait git_installer.exe /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
        del git_installer.exe
        set "PATH=%PATH%;C:\Program Files\Git\cmd"
        
        git --version >nul 2>&1
        if !errorlevel! neq 0 (
            set "ERR_MSG=Git could not be installed automatically. Please install manually from git-scm.com"
            goto :FAILURE
        )
    )
    echo Git installed successfully.
) else (
    echo Git is already installed.
)

echo [2/10] CLONING SERVER FILES FROM GITHUB...
:: Prevent Git from hanging on a credentials prompt if the repo is private/unavailable
set GIT_TERMINAL_PROMPT=0

if not exist "%~dp0app.py" (
    echo Downloading server files from %REPO_URL%...
    git clone %REPO_URL% temp_repo >> "%LOGFILE%" 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo ======================================================================
        echo WARNING: We were not able to download the server files from GitHub.
        echo Please contact the owner ^(Keiran Geverding^) for file access.
        echo ======================================================================
        echo.
        echo [WARN] Git clone authentication/download failed. >> "%LOGFILE%"
        echo Press any key to acknowledge this warning...
        pause >nul
    ) else (
        echo Copying files to root directory...
        xcopy /s /e /y /h temp_repo\* "%~dp0" >> "%LOGFILE%" 2>&1
        rd /s /q temp_repo
        echo [LOG] Repo cloned successfully. >> "%LOGFILE%"
    )
) else (
    echo Server files already detected in root folder. Skipping clone.
)

echo [3/10] CHECKING PYTHON...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOG] Python not found. Prompting manual install to avoid AV false positives. >> "%LOGFILE%"
    echo.
    echo ======================================================================
    echo Python was not found on this system.
    echo To prevent Antivirus warnings, this script cannot download it for you.
    echo.
    echo Please install Python manually:
    echo 1. Your browser will now open to the official Python download page.
    echo 2. Download the latest Windows installer.
    echo 3. IMPORTANT: Check "Add python.exe to PATH" at the bottom of the installer!
    echo 4. Complete the installation.
    echo ======================================================================
    echo.
    echo Opening browser...
    start %PYTHON_URL%
    echo Press any key AFTER you have successfully installed Python...
    pause >nul

    :: Refreshing PATH for this session only in case the system environment hasn't updated
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        :: Try finding the most common install paths for Python 3.10 to 3.12
        for %%V in (312 311 310) do (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            ) else if exist "C:\Program Files\Python%%V\python.exe" (
                set "PYTHON_CMD=C:\Program Files\Python%%V\python.exe"
            )
        )
        
        if defined PYTHON_CMD (
            echo [LOG] Found Python manually at: !PYTHON_CMD! >> "%LOGFILE%"
        ) else (
            echo ERROR: Could not locate Python after manual install. >> "%LOGFILE%"
            set "ERR_MSG=Python was not found. Please restart your computer and try running setup again."
            goto :FAILURE
        )
    ) else (
        set "PYTHON_CMD=python"
    )
) else (
    set "PYTHON_CMD=python"
    echo Python is already installed.
)

echo [4/10] PREPARING DIRECTORIES...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" >> "%LOGFILE%" 2>&1

echo [5/10] DOWNLOADING NPRI DATASETS...
set "BASE_URL=https://data-donnees.az.ec.gc.ca/api/file?path=%%2Fsubstances%%2Fplansreports%%2Freporting-facilities-pollutant-release-and-transfer-data%%2Fbulk-data-files-for-all-years-releases-disposals-transfers-and-facility-locations%%2F"
set "DATASET_FAILED=0"

:: Download logic with individual error checks (CSVs are safe and won't trigger AV)
for %%F in (NPRI-INRP_ReleasesRejets_1993-present.csv:NPRI_Releases.csv NPRI-INRP_DisposalsEliminations_1993-present.csv:NPRI_Disposals.csv NPRI-INRP_DisposalsEliminations_TransfersTransferts_1993-present.csv:NPRI_Transfers.csv NPRI-INRP_GeolocationsGeolocalisation_1993-present.csv:NPRI_Geolocations.csv) do (
    for /f "tokens=1,2 delims=:" %%A in ("%%F") do (
        echo   - Downloading %%B...
        :: -f flag forces curl to fail on HTTP errors like 404
        curl -f -L "%BASE_URL%%%A" -o "data\%%B" >> "%LOGFILE%" 2>&1
        if !errorlevel! neq 0 (
            echo WARNING: Could not download %%B. Check logs.
            echo [WARN] Failed to download %%B >> "%LOGFILE%"
            set "DATASET_FAILED=1"
        )
    )
)

if !DATASET_FAILED! equ 1 (
    echo.
    echo ======================================================================
    echo WARNING: Automatic NPRI data base failed to download from the government.
    echo Please visit https://open.canada.ca/data/en/dataset/40e01423-7728-429c-ac9d-2954385ccdfb
    echo to attempt a manual download.
    echo.
    echo Files required are:
    echo  - NPRI-INRP_ReleasesRejets_1993-present.csv
    echo  - NPRI-INRP_DisposalsEliminations_1993-present.csv
    echo  - NPRI-INRP_DisposalsEliminations_TransfersTransferts_1993-present.csv
    echo  - NPRI-INRP_GeolocationsGeolocalisation_1993-present.csv
    echo ======================================================================
    echo.
    echo Press any key to acknowledge this warning and continue setup...
    pause >nul
)

echo [6/10] CREATING VIRTUAL ENVIRONMENT...
"!PYTHON_CMD!" -m venv %VENV_DIR% >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    set "ERR_MSG=Failed to create Virtual Environment. Ensure Python was installed correctly."
    goto :FAILURE
)

echo [7/10] INSTALLING PACKAGES...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    set "ERR_MSG=Virtual environment activation script missing."
    goto :FAILURE
)

call %VENV_DIR%\Scripts\activate.bat
echo Upgrading Pip...
python -m pip install --upgrade pip >> "%LOGFILE%" 2>&1
if exist requirements.txt (
    echo Installing requirements.txt...
    pip install -r requirements.txt >> "%LOGFILE%" 2>&1
)
echo Installing Streamlit...
pip install streamlit >> "%LOGFILE%" 2>&1


echo [8/10] SEARCHING FOR %EXE_NAME%...
set "EXE_SOURCE_PATH="

:: Search current folder and subfolders (excluding VENV to save time)
for /f "delims=" %%i in ('dir /s /b /a-d "%~dp0%EXE_NAME%" 2^>nul ^| findstr /v /i "%VENV_DIR%"') do (
    set "EXE_SOURCE_PATH=%%i"
    echo Found: %%i >> "%LOGFILE%"
    goto :ProcessExe
)

:: If not found, trigger the UI workflow
if not defined EXE_SOURCE_PATH (
    echo [WARN] %EXE_NAME% not found. Prompting user. >> "%LOGFILE%"
    
    :: Show Message Box using PowerShell
    powershell -Command "Add-Type -AssemblyName PresentationFramework; $msg = 'The main app (%EXE_NAME%) is missing. Would you like to select the file to upload it to the kiosk_app folder?'; $result = [System.Windows.MessageBox]::Show($msg, 'Missing Executable', 'YesNo', 'Warning'); if ($result -eq 'No') { exit 1 } else { exit 0 }"
    
    if !errorlevel! equ 0 (
        echo Opening File Selection Dialog...
        :: Open File Dialog and capture the result
        for /f "delims=" %%I in ('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.OpenFileDialog; $f.Filter = 'Executable Files (*.exe)^|*.exe'; $f.Title = 'Select %EXE_NAME%'; [void]$f.ShowDialog(); $f.FileName"') do set "SELECTED_FILE=%%I"
        
        if defined SELECTED_FILE (
            if not exist "%KIOSK_DIR%" mkdir "%KIOSK_DIR%"
            echo Copying selected file to %KIOSK_DIR%...
            copy /y "!SELECTED_FILE!" "%~dp0%KIOSK_DIR%\%EXE_NAME%" >> "%LOGFILE%" 2>&1
            set "EXE_SOURCE_PATH=%~dp0%KIOSK_DIR%\%EXE_NAME%"
        ) else (
            echo User cancelled file selection. >> "%LOGFILE%"
        )
    )
)

:ProcessExe
echo [9/10] CONFIGURING WINDOWS STARTUP AND SHORTCUTS...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "PROJECT_DIR=%~dp0"

:: Handle Streamlit Server Launcher (Using VBS for silent execution)
echo Creating Silent Server Launcher (VBS)...
set "LAUNCHER_VBS=%STARTUP_DIR%\StartNPRIApp.vbs"
(
echo Set WinScriptHost = CreateObject^("WScript.Shell"^)
echo WinScriptHost.CurrentDirectory = "%PROJECT_DIR%"
echo WinScriptHost.Run "cmd /c venv\Scripts\streamlit run app.py --server.port %PORT%", 0
echo Set WinScriptHost = Nothing
) > "%LAUNCHER_VBS%" 2>> "%LOGFILE%"
echo [LOG] Created silent VBS startup script. >> "%LOGFILE%"

:: Handle EXE shortcuts
if defined EXE_SOURCE_PATH (
    echo Creating Desktop and Startup shortcuts for %EXE_NAME%...
    powershell -Command "$s = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $startup = [Environment]::GetFolderPath('Startup'); $lnk1 = $s.CreateShortcut([System.IO.Path]::Combine($desktop, 'NPRI Viewer.lnk')); $lnk1.TargetPath = '!EXE_SOURCE_PATH!'; $lnk1.WorkingDirectory = '%PROJECT_DIR%'; $lnk1.Save(); $lnk2 = $s.CreateShortcut([System.IO.Path]::Combine($startup, 'NPRI Viewer.lnk')); $lnk2.TargetPath = '!EXE_SOURCE_PATH!'; $lnk2.WorkingDirectory = '%PROJECT_DIR%'; $lnk2.Save();" >> "%LOGFILE%" 2>&1
    echo [LOG] Shortcuts created successfully. >> "%LOGFILE%"
)

echo [10/10] LAUNCHING STREAMLIT...
echo SETUP COMPLETE: %date% %time% >> "%LOGFILE%"
echo -------------------------------------------------
echo Server starting on http://localhost:%PORT%
echo -------------------------------------------------
streamlit run app.py --server.port %PORT%
if %errorlevel% neq 0 (
    set "ERR_MSG=Streamlit failed to start. Check if app.py exists."
    goto :FAILURE
)
goto :EOF

:FAILURE
echo.
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo   CRITICAL ERROR: %ERR_MSG%
echo   Details logged to: %LOGFILE%
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
echo Press any key to close this window...
pause
:: Keeps the window open even if pause fails
cmd /k