name "fabric-plugin"

default_version "1.4.1"

source :git => "https://github.com/cloudify-cosmo/cloudify-fabric-plugin"

build do
  command "[ -d /opt/cfy/plugins/fabric-plugin ] || mkdir -p /opt/cfy/plugins/fabric-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/fabric-plugin/plugin.yaml"
end
