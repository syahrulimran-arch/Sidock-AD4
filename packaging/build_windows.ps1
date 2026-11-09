[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipInnoInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot ".build"
$EnvironmentPath = Join-Path $BuildRoot "conda-env"
$SpecPath = Join-Path $PSScriptRoot "SIDock.spec"
$InstallerScript = Join-Path $PSScriptRoot "installer\SIDock.iss"

function Find-Conda {
    $command = Get-Command conda -ErrorAction SilentlyContinue
    if ($command) {
        if ($command.CommandType -eq "Application") { return $command.Source }
        return "conda"
    }

    $candidates = @(
        "$env:USERPROFILE\miniforge3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniforge3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw "Conda was not found. Install Miniforge, or run this file from Miniforge Prompt."
}

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Program $Arguments"
    }
}

Write-Host "SIDock AD4 0.7.6 installer build" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null

$Conda = Find-Conda
if (-not (Test-Path (Join-Path $EnvironmentPath "python.exe"))) {
    Write-Host "Creating the isolated Windows build environment..." -ForegroundColor Cyan
    Invoke-Checked $Conda @(
        "create", "--yes", "--prefix", $EnvironmentPath, "-c", "conda-forge",
        "python=3.11", "rdkit", "pyside6", "numpy", "scipy", "gemmi",
        "openbabel", "pytest", "pyinstaller", "pyinstaller-hooks-contrib", "pip"
    )
}

Write-Host "Installing SIDock and Meeko into the build environment..." -ForegroundColor Cyan
$EnvironmentPython = Join-Path $EnvironmentPath "python.exe"
$EnvironmentBin = Join-Path $EnvironmentPath "Library\bin"
$EnvironmentScripts = Join-Path $EnvironmentPath "Scripts"
$env:CONDA_PREFIX = $EnvironmentPath
$env:PATH = "$EnvironmentPath;$EnvironmentScripts;$EnvironmentBin;$env:PATH"
Invoke-Checked $EnvironmentPython @(
    "-m", "pip", "install", "--disable-pip-version-check",
    "meeko>=0.6,<0.8"
)
Invoke-Checked $EnvironmentPython @(
    "-m", "pip", "install", "--disable-pip-version-check",
    "--no-deps", $ProjectRoot
)

if (-not $SkipTests) {
    Write-Host "Running SIDock tests..." -ForegroundColor Cyan
    Invoke-Checked $EnvironmentPython @(
        "-m", "pytest", "-q", (Join-Path $ProjectRoot "tests")
    )
}

$DistPath = Join-Path $ProjectRoot "dist"
$WorkPath = Join-Path $BuildRoot "pyinstaller"
$SIDockDist = Join-Path $DistPath "SIDock"
$LegacyDockFlowDist = Join-Path $DistPath "DockFlow"
if (Test-Path $SIDockDist) {
    Remove-Item -Recurse -Force $SIDockDist
}
if (Test-Path $LegacyDockFlowDist) {
    Remove-Item -Recurse -Force $LegacyDockFlowDist
}
Write-Host "Freezing SIDock and its scientific runtime..." -ForegroundColor Cyan
Invoke-Checked $EnvironmentPython @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", $DistPath,
    "--workpath", $WorkPath, $SpecPath
)

# Conda stores the Shiboken/Qt and scientific runtime DLLs in Library\bin.
# PyInstaller does not consistently discover that directory when the project
# path contains spaces. Copying the DLL set is reliable and was verified on the
# same clean installed build used to diagnose the original startup failure.
$FrozenRuntime = Join-Path $SIDockDist "_internal"
if (-not (Test-Path $FrozenRuntime)) {
    throw "PyInstaller did not create dist\SIDock\_internal."
}
Copy-Item -Force (Join-Path $EnvironmentBin "*.dll") $FrozenRuntime

$FrozenExecutable = Join-Path $SIDockDist "SIDock.exe"
if (-not (Test-Path $FrozenExecutable)) {
    throw "PyInstaller did not create dist\SIDock\SIDock.exe."
}
Write-Host "Testing the packaged GUI and scientific runtime..." -ForegroundColor Cyan
Invoke-Checked $FrozenExecutable @("--self-test")

$InnoCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $InnoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc -and -not $SkipInnoInstall) {
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($Winget) {
        Write-Host "Installing Inno Setup 6 through Windows Package Manager..." -ForegroundColor Cyan
        Invoke-Checked $Winget.Source @(
            "install", "--id", "JRSoftware.InnoSetup", "--exact", "--silent",
            "--accept-source-agreements", "--accept-package-agreements"
        )
        $Iscc = $InnoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
}
if (-not $Iscc) {
    throw "Inno Setup 6 was not found. Install it, then rerun Build-Installer.bat."
}

Write-Host "Compiling the Setup EXE..." -ForegroundColor Cyan
Invoke-Checked $Iscc @($InstallerScript)

$SetupPath = Join-Path $DistPath "installer\SIDock_AD4_Setup_v0.7.6.exe"
if (-not (Test-Path $SetupPath)) {
    throw "The installer compiler finished but the expected Setup EXE was not created."
}
Write-Host "Finished: $SetupPath" -ForegroundColor Green
