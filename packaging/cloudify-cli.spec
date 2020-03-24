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

BuildRequires: python >= 2.7, python-virtualenv
Requires:       python >= 2.7


%description
Cloudify CLI


%prep

%build
virtualenv %_cli_env
%_cli_env/bin/pip install -r "${RPM_SOURCE_DIR}/dev-requirements.txt"
%_cli_env/bin/pip install "${RPM_SOURCE_DIR}"

# Jinja2 includes 2 files which will only be imported if async is available,
# but rpmbuild's brp-python-bytecompile falls over when it finds them. Here
# we remove them.
rm -f %_cli_env/lib/python2.7/site-packages/jinja2/async*.py

%install
mkdir -p %{buildroot}/opt
mkdir -p %{buildroot}/usr/bin
mv %_cli_env %{buildroot}%_cli_env
ln -s %_cli_env/bin/cfy %{buildroot}/usr/bin/cfy

%files
/opt/cfy
/usr/bin/cfy
