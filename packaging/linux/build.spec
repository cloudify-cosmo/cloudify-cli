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

[ ! -z $pip ] || curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | python2.7 &&
pip install setuptools==18.1
pip install wheel==0.24.0
yum -y install git python-devel gcc libxslt-devel libxml2-devel
curl http://cloudify-public-repositories.s3.amazonaws.com/cloudify-manager-blueprints/%{CORE_TAG_NAME}/cloudify-manager-blueprints.tar.gz -o /tmp/cloudify-manager-blueprints.tar.gz &&

alias python=python2.7

%build
%install

# Download or create wheels of all dependencies

pip wheel virtualenv==13.1.0 --wheel-dir %{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-rest-client@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-plugins-common@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-script-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-fabric-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-openstack-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-aws-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/tosca-vcloud-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-vsphere-plugin@%{PLUGINS_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&
pip wheel git+https://github.com/cloudify-cosmo/cloudify-cli@%{CORE_TAG_NAME} --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} &&

# Make directories

mkdir -p %{buildroot}/opt/cfy/cloudify-manager-blueprints-commercial &&
mkdir -p %{buildroot}/opt/cfy/cloudify/types &&
mkdir -p %{buildroot}/opt/cfy/cloudify/scripts &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/fabric-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/script-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/diamond-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/openstack-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/aws-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/vsphere-plugin &&
mkdir -p %{buildroot}/opt/cfy/cloudify/plugins/tosca-vcloud-plugin &&

# Copy LICENSE file
cp /vagrant/LICENSE %{buildroot}/opt/cfy/ &&

# Download manager-blueprints
tar -zxvf /tmp/cloudify-manager-blueprints.tar.gz --strip-components=1 -C %{buildroot}/opt/cfy/cloudify-manager-blueprints-commercial &&

# Download plugin.yaml files to local plugins folder

curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-fabric-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/fabric-plugin/plugin.yaml &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-script-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/script-plugin/plugin.yaml &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-diamond-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/diamond-plugin/plugin.yaml &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-openstack-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/openstack-plugin/plugin.yaml &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-aws-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/aws-plugin/plugin.yaml &&
curl https://raw.githubusercontent.com/cloudify-cosmo/tosca-vcloud-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/tosca-vcloud-plugin/plugin.yaml &&


# Clone and copy commercial plugin.yaml files to local plugins folder

curl -L --user %{GITHUB_USERNAME}:%{GITHUB_PASSWORD} https://raw.githubusercontent.com/cloudify-cosmo/cloudify-vsphere-plugin/%{PLUGINS_TAG_NAME}/plugin.yaml -o %{buildroot}/opt/cfy/cloudify/plugins/vsphere-plugin/plugin.yaml &&

# Download types.yaml
curl http://getcloudify.org.s3.amazonaws.com/spec/cloudify/%{CORE_TAG_NAME}/types.yaml -o %{buildroot}/opt/cfy/cloudify/types/types.yaml &&

# Download scripts to local scripts folder

curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/fs/mkfs.sh -o %{buildroot}/opt/cfy/cloudify/scripts/mkfs.sh
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/fs/fdisk.sh -o %{buildroot}/opt/cfy/cloudify/scripts/fdisk.sh
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/fs/mount.sh -o %{buildroot}/opt/cfy/cloudify/scripts/mount.sh
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/fs/unmount.sh -o %{buildroot}/opt/cfy/cloudify/scripts/unmount.sh
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/policies/host_failure.clj -o %{buildroot}/opt/cfy/cloudify/scripts/host_failure.clj
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/policies/threshold.clj -o %{buildroot}/opt/cfy/cloudify/scripts/threshold.clj
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/policies/ewma_stabilized.clj -o %{buildroot}/opt/cfy/cloudify/scripts/ewma_stabilized.clj
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/%{CORE_TAG_NAME}/resources/rest-service/cloudify/triggers/execute_workflow.clj -o %{buildroot}/opt/cfy/cloudify/scripts/execute_workflow.clj

%pre
%post

if ! which virtualenv >> /dev/null; then
    pip install --use-wheel --no-index --find-links=/var/wheels/%{name} virtualenv
fi
virtualenv /opt/cfy/env &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-vsphere-plugin --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-fabric-plugin --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-openstack-plugin --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-aws-plugin --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-vcloud-plugin --pre &&
/opt/cfy/env/bin/pip install --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-vsphere-plugin --pre &&

# replace all https links at types.yaml to local paths for offline usage
sed -i -e 's/https:\/\/raw\.githubusercontent\.com\/cloudify-cosmo\/cloudify-manager\/.*\/resources\/rest-service\/cloudify\/.*\//file:\/opt\/cfy\/cloudify\/scripts\//g' /opt/cfy/cloudify/types/types.yaml &&

# Add import resolver configuration section to the Cloudify configuration file (config.yaml) for offline usage
cat <<EOT >> /opt/cfy/env/lib/python2.7/site-packages/cloudify_cli/resources/config.yaml &&

import_resolver:
  parameters:
    rules:
    - {'http://www.getcloudify.org/spec/cloudify/%{CORE_TAG_NAME}/types.yaml': 'file:/opt/cfy/cloudify/types/types.yaml'}
    - {'http://www.getcloudify.org/spec/fabric-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/fabric-plugin'}
    - {'http://www.getcloudify.org/spec/script-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/script-plugin'}
    - {'http://www.getcloudify.org/spec/diamond-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/diamond-plugin'}
    - {'http://www.getcloudify.org/spec/openstack-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/openstack-plugin'}
    - {'http://www.getcloudify.org/spec/aws-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/aws-plugin'}
    - {'http://www.getcloudify.org/spec/vsphere-plugin/%{PLUGINS_TAG_NAME}': 'file:/opt/cfy/cloudify/plugins/vsphere-plugin'}
EOT



echo "You can now source /opt/cfy/env/bin/activate to start using Cloudify."

%preun
%postun

rm -rf /opt/cfy
rm -rf /var/wheels/${name}


%files

%defattr(-,root,root)
/var/wheels/%{name}/*.whl
/opt/cfy

