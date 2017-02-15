name "openstack-plugin"

plugin_version = "openstack-plugin/2.0"
default_version plugin_version.sub! "openstack-plugin/", ""

source :git => "https://github.com/cloudify-cosmo/cloudify-openstack-plugin"

build do
  command "[ -d /opt/cfy/plugins/openstack-plugin ] || mkdir -p /opt/cfy/plugins/openstack-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/openstack-plugin/plugin.yaml"
end
