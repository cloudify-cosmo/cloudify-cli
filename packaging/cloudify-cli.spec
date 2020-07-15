%define __python /opt/cfy/bin/python
%define _cli_env /opt/cfy

Name:           cloudify-cli
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify CLI
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-cli
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires: python3 >= 3.6
Requires:       python3 >= 3.6


%description
Cloudify CLI


%prep

%build
python3 -m venv %_cli_env
%_cli_env/bin/pip install -r "${RPM_SOURCE_DIR}/dev-requirements.txt"
%_cli_env/bin/pip install "${RPM_SOURCE_DIR}"


%install
mkdir -p %{buildroot}/opt
mkdir -p %{buildroot}/usr/bin
mv %_cli_env %{buildroot}%_cli_env
ln -s %_cli_env/bin/cfy %{buildroot}/usr/bin/cfy

%files
/opt/cfy
/usr/bin/cfy
