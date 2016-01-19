<powershell>

$is_dir_vagrant = Test-Path c:\vagrant
if (-Not $is_dir_vagrant) { mkdir c:\vagrant }

# kitchen default user-data minus winrm port open
$logfile="C:\Program Files\Amazon\Ec2ConfigService\Logs\kitchen-ec2.log"
#PS Remoting and & winrm.cmd basic config
Enable-PSRemoting -Force -SkipNetworkProfileCheck
& winrm.cmd set winrm/config '@{MaxTimeoutms="1800000"}' >> $logfile
& winrm.cmd set winrm/config/winrs '@{MaxMemoryPerShellMB="1024"}' >> $logfile
& winrm.cmd set winrm/config/winrs '@{MaxShellsPerUser="50"}' >> $logfile
#Server settings - support username/password login
& winrm.cmd set winrm/config/service/auth '@{Basic="true"}' >> $logfile
& winrm.cmd set winrm/config/service '@{AllowUnencrypted="true"}' >> $logfile
& winrm.cmd set winrm/config/winrs '@{MaxMemoryPerShellMB="1024"}' >> $logfile
"Disabling Complex Passwords" >> $logfile
$seccfg = [IO.Path]::GetTempFileName()
& secedit.exe /export /cfg $seccfg >> $logfile
(Get-Content $seccfg) | Foreach-Object {$_ -replace "PasswordComplexity\s*=\s*1", "PasswordComplexity = 0"} | Set-Content $seccfg
& secedit.exe /configure /db $env:windir\security\new.sdb /cfg $seccfg /areas SECURITYPOLICY >> $logfile
& cp $seccfg "c:\"
& del $seccfg
$username="vagrant"
$password="vagrant"
"Creating static user: $username" >> $logfile
& net.exe user /y /add $username $password >> $logfile
"Adding $username to Administrators" >> $logfile
& net.exe localgroup Administrators /add $username >> $logfile

# install chocolatey and packages
set-executionpolicy bypass -force
iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))

$choco_packages = @()
$ChocoPackage = new-object psobject -Property @{
        name = $null
        version = $null
}
function ChocoPackage {
        param(
                [Parameter(Mandatory=$true)]
                [String]$name,
                [Parameter(Mandatory=$false)]
                [String]$version
        )
        $pkg = $ChocoPackage.psobject.copy()
        $pkg.name = $name
        $pkg.version = $version
        $pkg
}

$cygwin = ChocoPackage -name cygwin -version 2.3.0
$cyg_get = ChocoPackage -name cyg-get -version 1.2.1
$cwrsync = ChocoPackage -name cwrsync -version 5.5.0

$choco_packages += $cygwin, $cyg_get, $cwrsync

foreach ($pkg in $choco_packages.getEnumerator()) {
	"installing {0}" -f $pkg.name
	if ($pkg.version) {
		$version = "--version={0}" -f $pkg.version
	} else {
		$version = ''
	}
	cinst -y $pkg.name $version
	if (!$?) { "[ERROR] choco install -y {0} {1}" -f $pkg.name, $version }
}
$env:Path += ";c:\tools\cygwin\bin"
Set-ItemProperty -Path 'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' -Name PATH -Value $env:Path
cyg-get openssh rsync
if (!$?) { "[ERROR] installing openssh rsync" }

$packages = @()
$Package = new-object psobject -Property @{
	name = $null
	url = $null
	args = $null
}
function Package {
	param(
		[Parameter(Mandatory=$true)]
		[String]$name,
		[Parameter(Mandatory=$true)]
		[String]$url,
		[Parameter(Mandatory=$false)]
		[String]$args
	)
	$pkg = $Package.psobject.copy()
	$pkg.name = $name
	$pkg.url = $url
	$pkg.args = $args
	$pkg
}
$Package | Add-Member -MemberType ScriptMethod -Name "filename" -Value {
	$this.url.split('/')[-1]
}
$Package | Add-Member -MemberType ScriptMethod -Name "filepath" -Value {
	"c:\\Windows\\Temp\\{0}" -f $this.filename()
}

# winsshd for rsync
$winsshd = Package -name winsshd -url https://bvdl.s3-eu-west-1.amazonaws.com/BvSshServer-Inst.exe -args '-defaultSite -startService -acceptEULA'
$vcforpy = Package -name msvcpp -url https://download.microsoft.com/download/7/9/6/796EF2E4-801B-4FC4-AB28-B59FBF6D907B/VCForPython27.msi -args '/qb ALLUSERS=1 /i c:\Windows\Temp\VCForPython27.msi'

$packages += $vcforpy, $winsshd

foreach ($pkg in $packages.GetEnumerator()) {
	"Downloading {0} from {1}" -f $pkg.name, $pkg.url
	(New-Object System.Net.WebClient).DownloadFile($pkg.url, $pkg.filepath())
	"Installing {0}" -f $pkg.name
	if ($pkg.filename() -match '.msi$') {
		Start-Process 'msiexec' -ArgumentList $pkg.args -NoNewWindow -Wait
	}
	if ($pkg.filename() -match '.exe$') {
		Start-Process $pkg.filepath() -ArgumentList $pkg.args -NoNewWindow -Wait
	}
}

# open winrm/ssh now
netsh advfirewall firewall add rule name="Windows Remote Management (HTTP-In)" dir=in action=allow protocol=TCP localport=5985 
netsh advfirewall firewall add rule name="SSHD" dir=in action=allow protocol=TCP localport=22

</powershell>
