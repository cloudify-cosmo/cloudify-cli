name "tosca-vcloud-plugin"

plugin_version = "tosca-vcloud-plugin/1.3.1"
default_version plugin_version.sub! "tosca-vcloud-plugin/", ""

source :git => "https://github.com/cloudify-cosmo/tosca-vcloud-plugin"

build do
  command "[ -d /opt/cfy/plugins/tosca-vcloud-plugin ] || mkdir -p /opt/cfy/plugins/tosca-vcloud-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/tosca-vcloud-plugin/plugin.yaml"
end

whitelist_file /.*/