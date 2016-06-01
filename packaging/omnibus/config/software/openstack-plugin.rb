name "openstack-plugin"

default_version "1.4"

source :git => "https://github.com/cloudify-cosmo/cloudify-openstack-plugin"

build do
  command "[ -d /opt/cfy/plugins/openstack-plugin ] || mkdir -p /opt/cfy/plugins/openstack-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/openstack-plugin/plugin.yaml"
end
