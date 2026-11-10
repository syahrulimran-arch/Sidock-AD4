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

Write-Host "SIDock AD4 0.7.10 installer build" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null

$Conda = Find-Conda
if (-not (Test-Path (Join-Path $EnvironmentPath "python.exe"))) {
    Write-Host "Creating the isolated Windows build environment..." -ForegroundColor Cyan
    Invoke-Checked $Conda @(
        "create", "--yes", "--prefix", $EnvironmentPath, "-c", "conda-forge",
        "python=3.11", "rdkit", "pyside6", "numpy", "scipy", "gemmi",
        "openbabel", "plip>=3,<4", "lxml", "pytest", "pyinstaller", "pyinstaller-hooks-contrib", "pip"
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
# The private Open Babel directory already contains this DLL. Retaining a
# second copy at _internal makes the Python binding and plugins register with
# different Open Babel instances, leaving PLIP without formats.
Remove-Item (Join-Path $FrozenRuntime "openbabel-3.dll") -Force -ErrorAction Stop

$FrozenExecutable = Join-Path $SIDockDist "SIDock.exe"
if (-not (Test-Path $FrozenExecutable)) {
    throw "PyInstaller did not create dist\SIDock\SIDock.exe."
}
Write-Host "Testing the packaged GUI and scientific runtime..." -ForegroundColor Cyan
$PluginDirectory = Join-Path $FrozenRuntime "tools\openbabel"
$PackagedPlugins = @(Get-ChildItem $PluginDirectory -Filter "*.obf" -File -ErrorAction Stop)
if ($PackagedPlugins.Count -eq 0) {
    throw "No packaged Open Babel .obf plugins were found."
}
Write-Host "Packaged Open Babel plugins: $($PackagedPlugins.Count)"
$SavedPath = $env:PATH
$SavedBabelLibDir = $env:BABEL_LIBDIR
$SavedBabelDataDir = $env:BABEL_DATADIR
$SavedPythonPath = $env:PYTHONPATH
$SavedCondaPrefix = $env:CONDA_PREFIX
try {
    $OpenBabelRoot = Join-Path $FrozenRuntime "tools\openbabel"
    $env:BABEL_LIBDIR = $PluginDirectory + "\"
    $env:BABEL_DATADIR = (Join-Path $OpenBabelRoot "data") + "\"
    $env:PYTHONPATH = ""
    $env:CONDA_PREFIX = ""
    $env:PATH = "$OpenBabelRoot;$FrozenRuntime;$env:SystemRoot\System32;$env:SystemRoot"

    $RequiredData = @("space-groups.txt", "atomtyp.txt", "bondtyp.txt", "element.txt", "types.txt")
    foreach ($DataFile in $RequiredData) {
        $DataPath = Join-Path $env:BABEL_DATADIR $DataFile
        if (-not (Test-Path $DataPath -PathType Leaf)) {
            throw "Required packaged Open Babel data file is missing: $DataPath"
        }
    }

    $FormatOutput = & (Join-Path $OpenBabelRoot "obabel.exe") -L formats 2>&1
    $FormatExit = $LASTEXITCODE
    $FormatOutput | Write-Host
    if ($FormatExit -ne 0 -or -not ($FormatOutput -match "(?m)^pdb\s+--") -or -not ($FormatOutput -match "(?m)^pdbqt\s+--")) {
        throw "Packaged obabel cannot load its PDB/PDBQT plugins."
    }

    $ProbePdb = Join-Path $BuildPath "openbabel-probe.pdb"
    $ProbePdbqt = Join-Path $BuildPath "openbabel-probe.pdbqt"
    @'
ATOM      1  N   ALA A   1      11.104  13.207   9.447  1.00 20.00           N
ATOM      2  CA  ALA A   1      12.560  13.330   9.280  1.00 20.00           C
ATOM      3  C   ALA A   1      13.151  12.027   8.748  1.00 20.00           C
ATOM      4  O   ALA A   1      12.558  10.963   8.918  1.00 20.00           O
END
'@ | Set-Content -Path $ProbePdb -Encoding ascii
    $ConversionOutput = & (Join-Path $OpenBabelRoot "obabel.exe") -ipdb $ProbePdb -opdbqt -O $ProbePdbqt -h --partialcharge gasteiger -xr -xc -xn -xh 2>&1
    $ConversionExit = $LASTEXITCODE
    $ConversionOutput | Write-Host
    $ProbeText = if (Test-Path $ProbePdbqt) { Get-Content $ProbePdbqt -Raw } else { "" }
    if ($ConversionExit -ne 0 -or $ConversionOutput -match "0 molecules converted|Cannot initialize database" -or $ProbeText -notmatch "(?m)^(ATOM|HETATM)") {
        throw "Packaged obabel failed a real PDB-to-PDBQT conversion."
    }

    $SelfTestOut = Join-Path $BuildPath "sidock-self-test.out"
    $SelfTestErr = Join-Path $BuildPath "sidock-self-test.err"
    $SelfTestProcess = Start-Process -FilePath $FrozenExecutable -ArgumentList "--self-test" -Wait -PassThru -RedirectStandardOutput $SelfTestOut -RedirectStandardError $SelfTestErr
    if (Test-Path $SelfTestOut) { Get-Content $SelfTestOut }
    if (Test-Path $SelfTestErr) { Get-Content $SelfTestErr }
    if ($SelfTestProcess.ExitCode -ne 0) {
        throw "Packaged runtime self-test failed with exit code $($SelfTestProcess.ExitCode)."
    }
}
finally {
    $env:PATH = $SavedPath
    $env:BABEL_LIBDIR = $SavedBabelLibDir
    $env:BABEL_DATADIR = $SavedBabelDataDir
    $env:PYTHONPATH = $SavedPythonPath
    $env:CONDA_PREFIX = $SavedCondaPrefix
}

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

$SetupPath = Join-Path $DistPath "installer\SIDock_AD4_Setup_v0.7.10.exe"
if (-not (Test-Path $SetupPath)) {
    throw "The installer compiler finished but the expected Setup EXE was not created."
}
Write-Host "Finished: $SetupPath" -ForegroundColor Green
