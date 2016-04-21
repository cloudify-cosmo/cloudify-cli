name "tosca-vcloud-plugin"

default_version "1.3.1"

source :git => "https://github.com/cloudify-cosmo/tosca-vcloud-plugin"

build do
  command "[ -d /opt/cfy/plugins/tosca-vcloud-plugin ] || mkdir -p /opt/cfy/plugins/tosca-vcloud-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/tosca-vcloud-plugin/plugin.yaml"
end

whitelist_file /.*/