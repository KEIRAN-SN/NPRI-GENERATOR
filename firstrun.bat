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
set "PYTHON_VER=3.12.2"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-amd64.exe"
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
    echo [LOG] Python not found. Starting fresh install. >> "%LOGFILE%"
    echo Python not found. Downloading installer...
    
    curl -L %PYTHON_URL% -o python_installer.exe
    if !errorlevel! neq 0 (
        echo WARNING: curl failed. Trying PowerShell fallback... >> "%LOGFILE%"
        powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile 'python_installer.exe'"
        if !errorlevel! neq 0 (
            echo ERROR: Download failed via both curl and PowerShell. >> "%LOGFILE%"
            set "ERR_MSG=Failed to download Python installer. Please check your internet connection."
            goto :FAILURE
        )
    )

    if not exist python_installer.exe (
        echo ERROR: python_installer.exe not found after download. >> "%LOGFILE%"
        set "ERR_MSG=Python installer was blocked or deleted by the system."
        goto :FAILURE
    )

    echo Installing Python %PYTHON_VER%... Please accept any UAC prompts.
    start /wait python_installer.exe PrependPath=1 Include_test=0
    del python_installer.exe

    :: Refreshing PATH for this session only
    set "PY_PATH=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if exist "!PY_PATH!" (
        set "PYTHON_CMD=!PY_PATH!"
        echo [LOG] Using manual path: !PY_PATH! >> "%LOGFILE%"
    ) else (
        set "PY_PATH=C:\Program Files\Python312\python.exe"
        if exist "!PY_PATH!" (
            set "PYTHON_CMD=!PY_PATH!"
        ) else (
            echo ERROR: Could not locate Python after install. >> "%LOGFILE%"
            set "ERR_MSG=Python was installed but the script cannot find the executable."
            goto :FAILURE
        )
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
    echo Installing Dependencies...
    pip install -r requirements.txt >> "%LOGFILE%" 2>&1
)
echo Installing Streamlit...
pip install streamlit >> "%LOGFILE%" 2>&1


:SearchEXE
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
    ) else (
        echo User declined upload. Prompting to build from source... >> "%LOGFILE%"
        
        :: Prompt user to build from source
        powershell -Command "Add-Type -AssemblyName PresentationFramework; $msg = 'Would you like the system to try and build the executable from the source code?'; $result = [System.Windows.MessageBox]::Show($msg, 'Build from Source?', 'YesNo', 'Question'); if ($result -eq 'No') { exit 1 } else { exit 0 }"
        
        if !errorlevel! equ 0 (
            echo [LOG] User opted to build from source. >> "%LOGFILE%"
            echo Installing required build packages ^(PyQt6, pynput, etc.^)...
            pip install PyQt6 PyQt6-WebEngine pynput pyinstaller >> "%LOGFILE%" 2>&1
            
            if exist "%~dp0kiosk_app\source\build_exe.bat" (
                echo Building the executable... This may take a few minutes.
                
                :: Change into the source directory to ensure the build script runs correctly
                pushd "%~dp0kiosk_app\source"
                call build_exe.bat >> "%LOGFILE%" 2>&1
                popd
                
                echo Build script finished. Rescanning for executable...
                goto :SearchEXE
            ) else (
                echo ERROR: build_exe.bat not found in %~dp0kiosk_app\source\ >> "%LOGFILE%"
                powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Could not find build_exe.bat in kiosk_app\source.', 'Build Error', 'OK', 'Error');"
            )
        ) else (
            echo User declined to build from source. >> "%LOGFILE%"
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