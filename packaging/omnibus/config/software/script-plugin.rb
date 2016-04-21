name "script-plugin"

default_version "1.4"

source :git => "https://github.com/cloudify-cosmo/cloudify-script-plugin"

build do
  command "[ -d /opt/cfy/plugins/script-plugin ] || mkdir -p /opt/cfy/plugins/script-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/script-plugin/plugin.yaml"
end