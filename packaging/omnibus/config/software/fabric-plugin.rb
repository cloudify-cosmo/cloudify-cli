name "fabric-plugin"

plugin_version = "fabric-plugin/1.5.2"
default_version plugin_version.sub! "fabric-plugin/", ""


source :git => "https://github.com/cloudify-cosmo/cloudify-fabric-plugin"

build do
  command "[ -d /opt/cfy/plugins/fabric-plugin ] || mkdir -p /opt/cfy/plugins/fabric-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/fabric-plugin/plugin.yaml"
end
