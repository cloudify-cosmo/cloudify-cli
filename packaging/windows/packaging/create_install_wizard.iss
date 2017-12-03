#define AppName "Cloudify CLI"
#define AppVersion GetEnv('VERSION')
#define AppMilestone GetEnv('PRERELEASE')
#define AppBuild GetEnv('BUILD')
#define AppPublisher "GigaSpaces Technologies"
#define AppURL "http://getcloudify.org/"
#define PluginsTagName GetEnv('PLUGINS_TAG_NAME')
#define CoreTagName GetEnv('CORE_TAG_NAME')

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{94B9D938-5123-4AC5-AA99-68F07F773DE2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={sd}\Cloudify
OutputBaseFilename=cloudify-windows-cli_{#AppVersion}-{#AppMilestone}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=
LicenseFile=source\license.txt
MinVersion=6.0
SetupIconFile=source\icons\Cloudify.ico
UninstallDisplayIcon={app}\Cloudify.ico
OutputDir=output\
DisableDirPage=auto
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "source\python\*"; DestDir: "{app}\embedded" ;Flags: recursesubdirs
Source: "source\wheels\*.whl"; Flags: dontcopy
Source: "source\icons\Cloudify.ico"; DestDir: "{app}"

Source: "source\types\*"; DestDir: "{app}\cloudify\types"; Flags: recursesubdirs
Source: "source\scripts\*"; DestDir: "{app}\cloudify\scripts"; Flags: recursesubdirs
Source: "source\plugins\*"; DestDir: "{app}\cloudify\plugins"; Flags: recursesubdirs
Source: "source\import_resolver.yaml"; Flags: dontcopy


[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon";

[Icons]
Name: "{userdesktop}\Cloudify CLI"; Filename: "{cmd}"; Parameters: "/k SET PATH=%PATH%;{app}\embedded\Scripts\"; WorkingDir: "{app}"; IconFilename: "{app}\Cloudify.ico"; Tasks: "desktopicon";

[UninstallDelete]
;this is NOT recommended but in our case, no user data here
Type: "filesandordirs"; Name: "{app}"

[Code]
const
  mainPackagesName = 'cloudify cloudify-fabric-plugin';
  //Error messages
  errUnexpected = 'Unexpected error. Run setup with /LOG flag and check the logs for additional details.';
  LF = #10;
  CR = #13;
  CRLF = CR + LF;

function runPipSetup(): Boolean;
var
  GetPipArgs: String;
  ErrorCode: Integer;
begin
  GetPipArgs := '-m ensurepip';
  Exec(Expandconstant('{app}\embedded\python.exe'), GetPipArgs, Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);
  Log('Installting pip return code: ' + IntToStr(ErrorCode));
  if Errorcode <> 0 then
    Result := False
  else
    Result := True;
end;


function runWheelsInstall(): Boolean;
var
  PipArgs: String;
  ErrorCode: Integer;
  PackagesToInstall: String;
begin
  ExtractTemporaryFiles('*.whl');

  PipArgs := 'install --pre --use-wheel --no-index --find-links . --force-reinstall --ignore-installed ' + mainPackagesName;
  Exec(Expandconstant('{app}\embedded\Scripts\pip.exe'), PipArgs, Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);
  Log('Installting wheels return code: ' + IntToStr(ErrorCode));

  //Pip seems to return errorcode 2 when it's not clean install
  if (Errorcode = 0) or (Errorcode = 2) then
    Result := True
  else
    Result := False;
end;

function updateConfigYaml(): Boolean;
var
  MappingStrings: TArrayOfString;
  ConfigYamlPath: String;
  Status: Boolean;
  Index: Integer;
begin
  ConfigYamlPath := Expandconstant('{%HOMEPATH}\.cloudify\config.yaml')
  ExtractTemporaryFile('import_resolver.yaml');
  Status := LoadStringsFromFile(ExpandConstant('{tmp}\import_resolver.yaml'), MappingStrings);

  if not Status then
  begin
    Result := False;
    Exit;
  end;

  for Index := 0 to GetArrayLength(MappingStrings) - 1 do
  begin
    // setting the path to cloudify dir path
    StringChangeEx(MappingStrings[Index], 'CLOUDIFY_PATH', Expandconstant('{app}'), True);
    // replacing the tags to a current one
    StringChangeEx(MappingStrings[Index], 'CORE_TAG_NAME', ExpandConstant('{#CoreTagName}'), True);
    StringChangeEx(MappingStrings[Index], 'PLUGINS_TAG_NAME', ExpandConstant('{#PluginsTagName}'), True);
    // replacing the end line from linux to both windows and linux
    StringChangeEx(MappingStrings[Index], LF, CRLF, False);
  end;
  Log('Saving new config: ' + ConfigYamlPath);
  Result := SaveStringsToFile(ConfigYamlPath, MappingStrings, True);

end;


//Install Pip, Wheels and update resolver during setup
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if not (runPipSetup and runWheelsInstall and updateConfigYaml) then
      RaiseException(errUnexpected);
  end;
end;
