%define _rpmdir /tmp

Name:           cloudify-%{DISTRO}-%{RELEASE}-cli
Version:        %{VERSION}
Release:        %{PRERELEASE}_b%{BUILD}
Summary:        Cloudify's CLI
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-cli
Vendor:         Gigaspaces Inc.
Prefix:         %{_prefix}
Packager:       Gigaspaces Inc.
BuildRoot:      %{_tmppath}/%{name}-root


%description

Cloudify's Command-Line Interface.



%prep

set +e
pip=$(which pip)
set -e

[ ! -z $pip ] || sudo curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python2.7 &&
sudo pip install setuptools==18.1
sudo pip install wheel==0.24.0
sudo yum -y install git python-devel gcc
sudo curl http://cloudify-public-repositories.s3.amazonaws.com/cloudify-manager-blueprints/%{CORE_TAG_NAME}/cloudify-manager-blueprints.tar.gz -o /tmp/cloudify-manager-blueprints.tar.gz &&

alias python=python2.7


%build
%install

# Download or create wheels of all dependencies

sudo pip wheel virtualenv==13.1.0 --wheel-dir %{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-rest-client@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-plugins-common@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-script-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-fabric-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-openstack-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-aws-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-vsphere-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-softlayer-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-cli@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&

# Copy LICENSE file

mkdir -p %{buildroot}/cfy &&
sudo cp /vagrant/LICENSE %{buildroot}/cfy/ &&


# Download manager-blueprints

mkdir -p %{buildroot}/cfy/cloudify-manager-blueprints-commercial &&
sudo tar -zxvf /tmp/cloudify-manager-blueprints.tar.gz --strip-components=1 -C %{buildroot}/cfy/cloudify-manager-blueprints-commercial &&



%pre
%post

if ! which virtualenv >> /dev/null; then
    pip install --use-wheel --no-index --find-links=/var/wheels/%{name} virtualenv
fi
virtualenv /cfy/env &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify --pre &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-vsphere-plugin --pre &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-softlayer-plugin --pre &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-fabric-plugin --pre &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-openstack-plugin --pre &&
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-aws-plugin --pre &&

echo "You can now source /cfy/env/bin/activate to start using Cloudify."



%preun
%postun

rm -rf /cfy
rm -rf /var/wheels/${name}



%files

%defattr(-,root,root)
/var/wheels/%{name}/*.whl
/cfy/LICENSE
/cfy/cloudify-manager-blueprints-commercial
