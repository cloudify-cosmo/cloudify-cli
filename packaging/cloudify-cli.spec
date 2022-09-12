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


%description
Cloudify CLI


%prep

%build

# First let's build Python 3.10 in a custom location
mkdir -p /opt/python3.10

mkdir -p /tmp/BUILD_SOURCES
cd /tmp/BUILD_SOURCES

# -- build & install OpenSSL 1.1.1, required for Python 3.10
curl https://ftp.openssl.org/source/openssl-1.1.1k.tar.gz -o openssl-1.1.1k.tar.gz
tar -xzvf openssl-1.1.1k.tar.gz
cd openssl-1.1.1k && ./config --prefix=/usr --openssldir=/etc/ssl --libdir=lib no-shared zlib-dynamic && make && make install
# -- build & install Python 3.10
cd ..
curl https://www.python.org/ftp/python/3.10.6/Python-3.10.6.tgz -o Python-3.10.6.tgz
tar xvf Python-3.10.6.tgz
cd Python-3.10.6 && sed -i 's/PKG_CONFIG openssl /PKG_CONFIG openssl11 /g' configure && ./configure --prefix=/opt/python3.10 && sudo make altinstall

# Create the venv with the custom Python symlinked in
/opt/python3.10/bin/python3.10 -m venv %_cli_env

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
