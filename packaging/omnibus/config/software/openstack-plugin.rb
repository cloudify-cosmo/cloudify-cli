name "openstack-plugin"
skip_transitive_dependency_licensing true

plugin_version = "openstack-plugin/2.0.1"
default_version plugin_version.sub! "openstack-plugin/", ""

source :git => "https://github.com/cloudify-cosmo/cloudify-openstack-plugin"

build do
  command "[ -d /opt/cfy/plugins/openstack-plugin ] || mkdir -p /opt/cfy/plugins/openstack-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/openstack-plugin/plugin.yaml"
end
