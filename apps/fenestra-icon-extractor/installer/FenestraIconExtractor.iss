; Inno Setup 6 script for Fenestra Icon Extractor.
; Built by ../build.sh (ISCC under Wine on Linux) or by CI on windows-latest.
; Pass /DSourceExe=<path to FenestraIconExtractor.exe> /DOutputDir=<dir>.

#define AppName "Fenestra Icon Extractor"
#define AppVersion "1.0.1"
#ifndef SourceExe
  #define SourceExe "..\out\portable\FenestraIconExtractor.exe"
#endif
#ifndef OutputDir
  #define OutputDir "..\out"
#endif

[Setup]
AppId={{6B0E2C1D-4F7A-4E8B-9C3D-FE5A0E1C7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Fenestra OS
AppPublisherURL=https://github.com/miguelcoxcaballero/fenestra-os
AppSupportURL=https://github.com/miguelcoxcaballero/fenestra-os/issues
DefaultDirName={autopf}\Fenestra Icon Extractor
DefaultGroupName=Fenestra
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=FenestraIconExtractorSetup
SetupIconFile=..\app.ico
UninstallDisplayIcon={app}\FenestraIconExtractor.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\FenestraIconExtractor.exe"; Comment: "Export your Windows icons, fonts and cursors for Fenestra OS"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\FenestraIconExtractor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FenestraIconExtractor.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
