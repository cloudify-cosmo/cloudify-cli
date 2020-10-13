#define AppName "Cloudify CLI"
#define AppVersion GetEnv('VERSION')
#define AppMilestone GetEnv('PRERELEASE')
#define AppBuild GetEnv('BUILD')
#define AppPublisher "Cloudify Platform"
#define AppURL "https://cloudify.co/"
#define PluginsTagName GetEnv('PLUGINS_TAG_NAME')
#define CoreTagName GetEnv('CORE_TAG_NAME')

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={commonpf}\Cloudify {#AppVersion}-{#AppMilestone} CLI
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputBaseFilename=cloudify-windows-cli_{#AppVersion}-{#AppMilestone}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64 arm64 ia64
ArchitecturesAllowed=x64 arm64 ia64
LicenseFile=source\license.txt
MinVersion=6.0
SetupIconFile=source\icons\Cloudify.ico
UninstallDisplayIcon={app}\Cloudify.ico
OutputDir=output\

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "C:\Program Files\Cloudify {#AppVersion}-{#AppMilestone} CLI\*"; DestDir: "{app}"; Excludes: "\__pycache__\*"; Flags: createallsubdirs recursesubdirs
Source: "source\icons\Cloudify.ico"; DestDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon";

[Icons]
Name: "{commondesktop}\Cloudify {#AppVersion}-{#AppMilestone} CLI"; Filename: "%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoExit -Command $env:Path=\""{app}\Scripts\;$env:Path\"";function prompt{{\""[Cloudify {#AppVersion}-{#AppMilestone} CLI] $($executionContext.SessionState.Path.CurrentLocation)>\""}"; WorkingDir: "{app}"; IconFilename: "{app}\Cloudify.ico"; Tasks: "desktopicon";
