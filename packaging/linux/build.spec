%define coreversion 3.3m3
%define pluginsversion 1.3m3

Name:           cloudify-cli
Version:        3.3.0
Release:        m3
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

[ ! -z $pip ] || sudo curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python2.7
sudo pip install setuptools==18.0.1

sudo curl http://cloudify-public-repositories.s3.amazonaws.com/cloudify-manager-blueprints/%{coreversion}/cloudify-manager-blueprints.tar.gz -o /tmp/cloudify-manager-blueprints.tar.gz


%build
%install

# Download or create wheels of all dependencies

sudo pip wheel virtualenv --wheel-dir %{buildroot}/var/wheels/%{name}
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-rest-client@%{coreversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@%{coreversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-plugins-common@%{coreversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-script-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-fabric-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-openstack-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-aws-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-vsphere-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-softlayer-plugin@%{pluginsversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-cli@%{coreversion} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name}
# when the cli is built for py2.6, unless argparse is put within `install_requires`, we'll have to enable this:
# if which yum; then
#   sudo pip wheel argparse=#SOME_VERSION# --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name}
# fi

# Copy get-pip.py

sudo cp /vagrant/linux/source/get-pip.py %{buildroot}/var/wheels/%{name}

# Copy LICENSE file

mkdir -p %{buildroot}/cfy
sudo cp /vagrant/LICENSE %{buildroot}/cfy/


# Download manager-blueprints

mkdir -p %{buildroot}/cfy/cloudify-manager-blueprints
sudo tar -zxvf /tmp/cloudify-manager-blueprints.tar.gz --strip-components=1 -C %{buildroot}/cfy/cloudify-manager-blueprints



%pre
%post

if ! which virtualenv >> /dev/null; then
    /var/wheels/%{name}/get-pip.py --use-wheel --no-index --find-links=/var/wheels/%{name} virtualenv
fi
virtualenv /cfy/env
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify --pre
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-vsphere-plugin --pre
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-softlayer-plugin --pre
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-fabric-plugin --pre
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-openstack-plugin --pre
/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-aws-plugin --pre
# when the cli is built for py2.6, unless argparse is put within `install_requires`, we'll have to enable this:
# if which yum; then
#   /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse argparse=#SOME_VERSION#
# fi

echo "You can now source /cfy/env/bin/activate to start using Cloudify."



%preun
%postun

rm -rf /cfy
rm -rf /var/wheels/${name}



%files

%defattr(-,root,root)
/var/wheels/%{name}/*.whl
/var/wheels/%{name}/get-pip.py
/cfy/LICENSE
/cfy/cloudify-manager-blueprints