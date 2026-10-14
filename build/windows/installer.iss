; Inno Setup script for the Windows installer.
;
;   iscc /DAppVersion=0.1.0 build\windows\installer.iss
;
; Installs for the current user by default (no administrator rights needed, which
; matters on hospital computers); an administrator can choose "all users" instead,
; which installs to Program Files. Adds a Start menu shortcut and an uninstaller.

#define AppName "REDCap Uploader"
#define AppExe "REDCap Uploader.exe"
#define Publisher "Yayasan RPRI"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define SourceDir "..\..\dist\REDCap Uploader"

[Setup]
AppId={{6B0E3A51-4C8D-4C57-9F0B-2A7E5D1C8B34}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=REDCap-Uploader-{#AppVersion}-Windows-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
