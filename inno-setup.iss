; Revision Tool installer. The user chooses the destination folder.

#define MyAppName "ReDeskLine"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Amir Pakdel"
#define MyAppURL "https://github.com/Amir-Pakdel"
#define MyAppExeName "ReDeskLine.exe"
#define ReleaseDir "src\build\windows\x64\runner\Release"
#define PythonDir "C:\Users\Admin\AppData\Local\Programs\Python\Python312"
#define VenvDir "C:\Users\Admin\Desktop\Deskline\.venv"

[Setup]
AppId={{8C4E1A72-6B2D-4F5E-9A10-3D7C6B8E1F24}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\{#MyAppName}
UsePreviousAppDir=no
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#SourcePath}
OutputBaseFilename=ReDeskLine-Setup
SetupIconFile={#SourcePath}\src\windows\runner\resources\app_icon.ico
Compression=zip
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
PrivilegesRequired=admin
RestartApplications=no
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "{#SourcePath}\{#ReleaseDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}\src\windows\runner\resources\app_icon.ico"; DestDir: "{app}"; DestName: "ReDeskLine.ico"
Source: "{#SourcePath}\deskline\*"; DestDir: "{app}\deskline"; Excludes: ".venv\*,__pycache__\*,*.pyc,.smoke\*,.git\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#VenvDir}\*"; DestDir: "{app}\deskline\.venv"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: string;
  ConfigText: string;
begin
  if CurStep <> ssPostInstall then
    Exit;
  ConfigFile := ExpandConstant('{app}\deskline\.venv\pyvenv.cfg');
  ConfigText :=
    'home = ' + ExpandConstant('{app}\python') + #13#10 +
    'include-system-site-packages = false' + #13#10 +
    'version = 3.12.10' + #13#10;
  SaveStringToFile(ConfigFile, ConfigText, False);
end;
