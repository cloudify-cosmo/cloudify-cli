name "diamond-plugin"

plugin_version = "diamond-plugin/1.3.14"
default_version plugin_version.sub! "diamond-plugin/", ""


source :git => "https://github.com/cloudify-cosmo/cloudify-diamond-plugin"

build do
  command "[ -d /opt/cfy/plugins/diamond-plugin ] || mkdir -p /opt/cfy/plugins/diamond-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/diamond-plugin/plugin.yaml"
end