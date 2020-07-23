param(
    $VERSION,
    $PRERELEASE,
    $DEV_BRANCH = "master",
    $UPLOAD = ""
)
Set-StrictMode -Version 1.0
$ErrorActionPreference="stop"
# Use TLSv1.2 for Invoke-Restmethod
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$CLI_PATH = "C:\Program Files\Cloudify CLI"
$GET_PIP_URL = "http://repository.cloudifysource.org/cloudify/components/win-cli-package-resources/get-pip-20.py"
$PIP_VERSION = "20.1.1"
$REPO_URL = "https://github.com/cloudify-cosmo/cloudify-cli/archive/$DEV_BRANCH.zip"
$PY_URL = "https://repository.cloudifysource.org/cloudify/components/python-3.6.8-embed-amd64.zip"
$INNO_SETUP_URL = "http://repository.cloudifysource.org/cloudify/components/win-cli-package-resources/inno_setup_6.exe"


function run {
    # Use this to get set -e alike behaviour, rather than running commands directly
    & $args[0] $args[1..($args.Length)]
    if ($LastExitCode -ne 0) {
        Write-Error "Error running @args"
    }
}


function rm_rf {
    # Because if you use "-ErrorAction Ignore" then you ignore all errors, not just
    # missing targets
    if (Test-Path $args[0]) {
        Remove-Item -Recurse -Force -Path $args[0]
    }
}


### Main ###

Write-Host "Deleting existing artifacts"
rm_rf python.zip
rm_rf get-pip.py
rm_rf "$CLI_PATH"
rm_rf inno_setup.exe

Write-Host "Checking whether Inno Setup needs installing..."
if (-Not (Test-Path "C:\Program Files (x86)\Inno Setup 6")) {
    Write-Host "Inno Setup not installed, downloading from $INNO_SETUP_URL"
    Invoke-RestMethod -Uri $INNO_SETUP_URL -OutFile inno_setup.exe
    Write-Host "Installing Inno Setup"
    # Cannot be invoked by run as it doesn't set LastExitCode
    & .\inno_setup.exe /VERYSILENT /SUPPRESSMSGBOXES
} else {
    Write-Host "Inno Setup is already installed."
}


# We use . because passing "" to the script causes the default to be used
if ( $DEV_BRANCH -ne "." ) {
    Write-Host "Deleting existing downloaded CLI."
    rm_rf cloudify-cli.zip
    rm_rf cloudify-cli
    Write-Host "Getting CLI repository from $REPO_URL"
    Invoke-RestMethod -Uri $REPO_URL -OutFile cloudify-cli.zip
    Expand-Archive -Path cloudify-cli.zip
    pushd cloudify-cli
        cd cloudify-cli-$DEV_BRANCH
            move * ..
        cd ..
        rm_rf cloudify-cli-$DEV_BRANCH
    popd
} else {
    Write-Host "Using local cloudify-cli directory."
}


Write-Host "Getting embeddable python from $PY_URL"
Invoke-RestMethod -Uri $PY_URL -OutFile python.zip

Write-Host "Getting get-pip from $GET_PIP_URL"
Invoke-RestMethod -Uri $GET_PIP_URL -OutFile get-pip.py


Write-Host "Preparing CLI path"
mkdir $CLI_PATH
Expand-Archive -Path python.zip -DestinationPath $CLI_PATH


# We need to expand this to make virtualenv work
pushd "$CLI_PATH"
    Expand-Archive -Path python36.zip
    rm_rf python36.zip
    mkdir Lib
    move python36\* Lib
    rmdir python36
popd


Write-Host "Adding pip to embedded python"
Set-Content -Path "$CLI_PATH\python36._pth" -Value ".
.\Lib
.\Lib\site-packages

import site"
run $CLI_PATH\python.exe get-pip.py pip==$PIP_VERSION


Write-Host "Installing CLI"
pushd cloudify-cli
    run $CLI_PATH\scripts\pip.exe install --prefix="$CLI_PATH" -r dev-requirements.txt
    run $CLI_PATH\scripts\pip.exe install --prefix="$CLI_PATH" .
popd


Write-Host "Building CLI package"
$env:VERSION = $VERSION
$env:PRERELEASE = $PRERELEASE
run "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" cloudify-cli\packaging\windows\packaging\create_install_wizard.iss


if ( $UPLOAD -eq "upload" ) {
    Write-Host "Preparing AWS CLI"
    run "$CLI_PATH\Scripts\pip.exe" install --prefix="$CLI_PATH" awscli
    Set-Content -Path "$CLI_PATH\scripts\aws.py" -Value "import awscli.clidriver
import sys
sys.exit(awscli.clidriver.main())"

    Write-Host "Uploading CLI to S3"
    pushd cloudify-cli\packaging\windows\packaging\output
        $artifact = "cloudify-windows-cli_$env:VERSION-$env:PRERELEASE.exe"
        $artifact_md5 = $(Get-FileHash -Path $artifact -Algorithm MD5).Hash
        $s3_path = "s3://cloudify-release-eu/cloudify/$env:VERSION/$env:PRERELEASE-build"
        run "$CLI_PATH\python.exe" "$CLI_PATH\Scripts\aws.py" s3 cp .\ $s3_path --acl public-read --recursive
    popd
} else {
    Write-Host "Not uploading as upload is set to '$UPLOAD' instead of 'upload'."
}
