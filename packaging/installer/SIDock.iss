#define MyAppName "SIDock AD4"
#define MyAppVersion "0.7.7"
#define MyAppPublisher "Dr Syahrul Imran"
#define MyAppExeName "SIDock.exe"

[Setup]
AppId={{A2DC8240-AE29-46F3-890E-847935F56061}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Developed by Dr Syahrul Imran
DefaultDirName={localappdata}\Programs\SIDock AD4
DefaultGroupName=SIDock AD4
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist\installer
OutputBaseFilename=SIDock_AD4_Setup_v0.7.7
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; PySide6/Qt 6 requires Windows 10 version 1809 (build 17763) or newer.
; This check also permits Windows 11, whose version/build is newer.
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=0.7.7.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany=Dr Syahrul Imran
VersionInfoDescription=SIDock AD4 virtual screening application

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\..\dist\SIDock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; The same AppId upgrades pre-0.7.0 installations in place. Remove obsolete
; product-name artifacts so the old executable and shortcuts cannot remain.
Type: files; Name: "{app}\DockFlow.exe"
Type: files; Name: "{userprograms}\DockFlow AD4\DockFlow AD4.lnk"
Type: dirifempty; Name: "{userprograms}\DockFlow AD4"
Type: files; Name: "{autodesktop}\DockFlow AD4.lnk"

[Icons]
Name: "{group}\SIDock AD4"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "SIDock AD4 — Developed by Dr Syahrul Imran"
Name: "{autodesktop}\SIDock AD4"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "SIDock AD4 — Developed by Dr Syahrul Imran"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SIDock AD4"; Flags: nowait postinstall skipifsilent
