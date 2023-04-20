%define __python /opt/cfy/bin/python
%define _cli_env /opt/cfy
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0

# Prevent mangling shebangs (RH8 build default), which fails
#  with the test files of networkx<2 due to RH8 not having python2.
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
#  separate from the official RH supplied software (due to a change in RH8)
%define _build_id_links none
%endif

Name:           cloudify-cli
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify CLI
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-cli
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

Source0:        https://cloudify-cicd.s3.amazonaws.com/python-build-packages/cfy-python3.11-%{ARCHITECTURE}-cli.tgz


%description
Cloudify CLI

%prep
sudo tar xf %{S:0} -C /

%build

# Create the venv with the custom Python symlinked in
/opt/cfy/python3.11/bin/python3.11 -m venv %_cli_env

%_cli_env/bin/pip install --upgrade pip
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
