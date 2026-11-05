; Instalador de Windows (Inno Setup 6) para Electronic Front Panel Designer.
; Compilar tras PyInstaller:  iscc /DAppVersion=1.0.0 packaging\windows\efpd.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Electronic Front Panel Designer"
#define AppExe "FrontPanelDesigner.exe"
#define Root "..\.."

[Setup]
AppId={{6E7B0C51-3B7A-4E0C-9C55-2F4E1D9A7F31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Aleluya-Git
AppPublisherURL=https://github.com/Aleluya-Git/Front-Panel-Designer
AppSupportURL=https://github.com/Aleluya-Git/Front-Panel-Designer/issues
AppUpdatesURL=https://github.com/Aleluya-Git/Front-Panel-Designer/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile={#Root}\LICENSE
OutputDir={#Root}\dist
OutputBaseFilename=FrontPanelDesigner-{#AppVersion}-Windows-x64-Setup
SetupIconFile={#Root}\efpd\resources\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocFileExtension,{#AppName},.efpd}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Root}\dist\FrontPanelDesigner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\ejemplos\*.efpd"; DestDir: "{app}\ejemplos"; Flags: ignoreversion
Source: "{#Root}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.es.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\{#AppName} - ejemplos"; Filename: "{app}\ejemplos"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.efpd"; ValueType: string; ValueName: ""; ValueData: "EFPD.Project"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\EFPD.Project"; ValueType: string; ValueName: ""; ValueData: "{#AppName} Project"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\EFPD.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\EFPD.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
