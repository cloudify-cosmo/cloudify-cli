name "diamond-plugin"

default_version "1.3.3"

source :git => "https://github.com/cloudify-cosmo/cloudify-diamond-plugin"

build do
  command "[ -d /opt/cfy/plugins/diamond-plugin ] || mkdir -p /opt/cfy/plugins/diamond-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/diamond-plugin/plugin.yaml"
end