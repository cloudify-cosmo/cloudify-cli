name "script-plugin"

plugin_version = "script-plugin/1.5.3"
default_version plugin_version.sub! "script-plugin/", ""

source :git => "https://github.com/cloudify-cosmo/cloudify-script-plugin"

build do
  command "[ -d /opt/cfy/plugins/script-plugin ] || mkdir -p /opt/cfy/plugins/script-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/script-plugin/plugin.yaml"
end