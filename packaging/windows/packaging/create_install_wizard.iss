#define AppName "Cloudify CLI"
#define AppVersion GetEnv('VERSION')
#define AppMilestone GetEnv('PRERELEASE')
#define AppBuild GetEnv('BUILD')
#define AppPublisher "GigaSpaces Technologies"
#define AppURL "http://getcloudify.org/"

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
DefaultDirName={pf}\Cloudify
DisableProgramGroupPage=yes
OutputBaseFilename=cloudify-windows-cli_{#AppVersion}-{#AppMilestone}-b{#AppBuild}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=
LicenseFile=source\license.txt
MinVersion=6.0
SetupIconFile=source\icons\Cloudify.ico
UninstallDisplayIcon={app}\Cloudify.ico
OutputDir=output\

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "source\python\python.msi"; Flags: dontcopy nocompression
Source: "source\wheels\*.whl"; Flags: dontcopy
Source: "source\pip\*"; Flags: dontcopy
Source: "source\virtualenv\*"; Flags: dontcopy
Source: "source\icons\Cloudify.ico"; DestDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon";

[Icons]
Name: "{userdesktop}\Cloudify CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\Scripts\activate.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\Cloudify.ico"; Tasks: "desktopicon";

[UninstallDelete]
;this is NOT recommended but in our case, no user data here
Type: "filesandordirs"; Name: "{app}"

[Code]
const
  mainPackageName = 'cloudify';
  //Registry key path
  RegPythonPath = 'SOFTWARE\Python\PythonCore\2.7\InstallPath';
  //Error messages
  errPythonMissing = 'Python installation was not found. In order to install {#AppName} you will need Python installed. Procceed to Python 2.7 installation?';
  errPipMissing = 'Pip was not found. Pip is a package management tool that is required to successfully install {#AppName}. Would you like to install it?';
  errVenvMissing = 'Virtualenv was not found. Virtualenv is a python environment managment tool that is required to successfully install {#AppName}. Would you like to install it?';
  errUnexpected = 'Unexpected error. Check install logs';
  infoPythonUninstall = 'Cloudify uninstaller will not remove Python as a safety precaution. Uninstalling Python should be done independently by the user';


function getPythonDir(): String;
var
  InstallPath: String;
begin
  RegQueryStringValue(HKLM, RegPythonPath, '', InstallPath);
  RegQueryStringValue(HKCU, RegPythonPath, '', InstallPath);
  Result := InstallPath;
end;


function isPythonInstalled(): Boolean;
begin
  if getPythonDir <> '' then
      Result := True
  else
      Result := False;
end;


function getPythonPath(): String;
var
  PythonPath: String;
begin
  if isPythonInstalled then begin
    PythonPath := AddBackslash(getPythonDir) + 'python.exe';
    if FileExists(PythonPath) then
      Result := PythonPath
  end;
end;


function runPythonSetup(): Boolean;
var
  PythonArgs: String;
  InstallerPath: String;
  ErrorCode: Integer;
begin
  ExtractTemporaryFile('python.msi');
  InstallerPath := Expandconstant('{tmp}\python.msi');
  PythonArgs := 'ADDDEFAULT=pip_feature';
  if WizardSilent then
    PythonArgs := PythonArgs + ' /qn';
  ShellExec('', InstallerPath, PythonArgs, '', SW_SHOW, ewWaituntilterminated, ErrorCode);

  if Errorcode <> 0 then
    Result := False
  else
    Result := True;
end;


function getPipPath(): String;
var
  PipPath: String;
begin
  if isPythonInstalled then begin
    PipPath := AddBackslash(getPythonDir) + 'Scripts\pip.exe';
    if FileExists(PipPath) then
      Result := PipPath
  end;
end;


function isPipInstalled(): Boolean;
begin
  if getPipPath <> '' then
      Result := True
  else
      Result := False;
end;


function runPipSetup(): Boolean;
var
  GetPipArgs: String;
  ErrorCode: Integer;
begin
  if isPythonInstalled then begin
    ExtractTemporaryFiles('*.whl');
    ExtractTemporaryFile('get-pip.py');
    GetPipArgs := 'get-pip.py --use-wheel --no-index --find-links .';
    ShellExec('', getPythonPath, GetPipArgs, Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);

    if Errorcode <> 0 then
      Result := False
    else
      Result := True;
    end;
end;


function getVenvPath(): String;
var
  VenvPath: String;
begin
  if isPythonInstalled then begin
    VenvPath := AddBackslash(getPythonDir) + 'Scripts\virtualenv.exe';
    if FileExists(VenvPath) then
      Result := VenvPath
  end;
end;


function isVenvInstalled(): Boolean;
begin
  if getVenvPath <> '' then
      Result := True
  else
      Result := False;
end;


function runVenvSetup(): Boolean;
var
  GetPipArgs: String;
  ErrorCode: Integer;
begin
  if isPythonInstalled then begin
    ExtractTemporaryFiles('*.whl');
    GetPipArgs := 'install --use-wheel --no-index --find-links . virtualenv';
    ShellExec('', getPipPath, GetPipArgs, Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);

    if Errorcode <> 0 then
      Result := False
    else
      Result := True;
    end;
end;


function runVenvInitialization(): Boolean;
var
  ErrorCode: Integer;
begin
  Exec(getVenvPath, Expandconstant('--clear "{app}"'), Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);

  if Errorcode <> 0 then
    Result := False
  else
    Result := True;
end;


function runWheelsInstall(): Boolean;
var
  PipArgs: String;
  ErrorCode: Integer;
begin
  ExtractTemporaryFiles('*.whl');

  if not (isVenvInstalled and runVenvInitialization) then begin
    Result := False;
    Exit;
  end;

  PipArgs := Expandconstant('/c set "VIRTUAL_ENV={app}" && set "PATH={app}\Scripts;%PATH%" && pip install --pre --use-wheel --no-index --find-links . --force-reinstall --ignore-installed ' + mainPackageName);
  Exec(Expandconstant('{sys}\cmd.exe'), PipArgs, Expandconstant('{tmp}'), SW_SHOW, ewWaituntilterminated, ErrorCode);

  if Errorcode <> 0 then
    Result := False
  else
    Result := True;
end;


//wrap MsgBox to handle silent install case
function getUserResponse(Message: String): Integer;
begin
  if not WizardSilent then
    Result := MsgBox(Message, mbError, MB_OKCANCEL)
  else
    Result := IDOK;
end;


//Pre-Assumptions: Python and pip are installed
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    if not runWheelsInstall then
      RaiseException(errUnexpected);
  end;
end;


//Check for pre-requirements (Python, Pip, Virtualenv)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  UserResponse: Integer;
begin
  if not isPythonInstalled then begin
    UserResponse := getUserResponse(errPythonMissing);
    if UserResponse <> IDOK then begin
      Result := 'Installation cannot continue without Python installed';
      Exit;
    end
    else if not runPythonSetup then begin
      Result := 'Python setup failed';
      Exit;
    end;
  end;

  if not isPipInstalled then begin
    UserResponse := getUserResponse(errPipMissing)
    if UserResponse <> IDOK then begin
      Result := 'Installation cannot continue without Pip installed';
      exit;
    end
    else if not runPipSetup then begin
      Result := 'Pip installation failed';
      Exit;
    end;
  end;

  if not isVenvInstalled then begin
    UserResponse := getUserResponse(errVenvMissing)
    if UserResponse <> IDOK then begin
      Result := 'Installation cannot continue without Virtualenv installed';
      Exit;
    end
    else if not runVenvSetup then begin
      Result := 'Virtualenv installation failed';
      Exit;
    end;
  end;
end;


//Display info message when install done about Python uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox(infoPythonUninstall, mbInformation, MB_OK);
end;