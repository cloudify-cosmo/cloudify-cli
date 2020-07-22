variable "VERSION" {}
variable "PRERELEASE" {}
variable "password" {}
variable "DEV_BRANCH" {}


provider "aws" {
  region = "eu-west-1"
}

data "aws_ami" "windows_cli_builder" {
  most_recent = true

  filter {
    name   = "name"
    values = ["Windows_Server-2016-English-Full-Base-*"]
  }

  owners = ["801119661308"] # This is the amazon owner ID for a bunch of their marketplace images
}

resource "aws_instance" "builder" {
  ami           = "${data.aws_ami.windows_cli_builder.id}"
  instance_type = "m3.medium"
  iam_instance_profile = "windows_agent_builder"

  tags = {
    Name = "Windows Agent Builder"
  }

  user_data = <<-EOT
    <powershell>
    $thumbprint = (New-SelfSignedCertificate -DnsName "winagentbuild" -CertStoreLocation Cert:\LocalMachine\My).ThumbPrint
    cmd.exe /c winrm quickconfig -q
    cmd.exe /c winrm set winrm/config '@{MaxTimeoutms="1800000"}'
    cmd.exe /c winrm set winrm/config/winrs '@{MaxMemoryPerShellMB="300"}'
    cmd.exe /c winrm set winrm/config/service '@{AllowUnencrypted="true"}'
    cmd.exe /c winrm set winrm/config/service/auth '@{Basic="true"}'
    cmd.exe /c winrm create "winrm/config/listener?Address=*+Transport=HTTPS" "@{Port=`"5986`"; Hostname=`"winagentbuild`"; CertificateThumbprint=`"$($Thumbprint)`"}"
    cmd.exe /c net stop winrm
    cmd.exe /c sc config winrm start= auto
    cmd.exe /c net start winrm
    netsh advfirewall firewall add rule name="WinRM 5985" protocol=TCP dir=in localport=5985 action=allow
    netsh advfirewall firewall add rule name="WinRM 5986" protocol=TCP dir=in localport=5986 action=allow
    netsh advfirewall firewall add rule name="RDP for troubleshooting" protocol=TCP dir=in localport=3389 action=allow
    $user = [ADSI]"WinNT://localhost/Administrator"
    $user.SetPassword("${var.password}")
    $user.SetInfo()
    # Allow older winrdp clients to connect (because remmina's clipboard sync is being unreliable)
    (Get-WmiObject -class Win32_TSGeneralSetting -Namespace root\cimv2\terminalservices -ComputerName $env:ComputerName -Filter "TerminalName='RDP-tcp'").SetUserAuthenticationRequired(0)
    </powershell>
  EOT

  provisioner "file" {
    source      = "win_cli_builder.ps1"
    destination = "C:\\Users\\Administrator\\win_cli_builder.ps1"
    connection {
      type     = "winrm"
      port     = 5986
      https    = true
      insecure = true
      user     = "Administrator"
      password = "${var.password}"
    }
  }

  provisioner "remote-exec" {
    inline = [ "powershell.exe -File C:\\Users\\Administrator\\win_cli_builder.ps1 \"${var.VERSION}\" \"${var.PRERELEASE}\" \"${var.DEV_BRANCH}\" \"upload\""]
    connection {
      type     = "winrm"
      port     = 5986
      https    = true
      insecure = true
      user     = "Administrator"
      password = "${var.password}"
    }
  }
}
