; Inno Setup script for Definitely Human(TM). Built by .github/workflows/release.yml.
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "Definitely Human"

[Setup]
AppId={{6E0C3F7A-2B54-4C59-9E7B-D4A000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Definitely Human
; ASCII path on purpose: a non-ASCII user name in C:\Users\... can break Python tooling.
DefaultDirName={sd}\DefinitelyHuman
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=DefinitelyHuman-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\assets\icon.ico
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
; the app writes its venv, model, settings and calibration here
Name: "{app}"; Permissions: users-modify

[Files]
Source: "..\build\app\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m definitely_human.cli serve --exit-when-closed"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m definitely_human.cli serve --exit-when-closed"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autoprograms}\{#AppName} - Repair"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"""; WorkingDir: "{app}"; StatusMsg: "Python, PyTorch ve model indiriliyor (~7 GB). Bu biraz surebilir..."; Flags: waituntilterminated
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m definitely_human.cli serve --exit-when-closed"; WorkingDir: "{app}"; Description: "{#AppName} uygulamasini ac"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
