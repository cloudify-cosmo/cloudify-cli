name "aws-plugin"

default_version "1.4"

source :git => "https://github.com/cloudify-cosmo/cloudify-aws-plugin"

build do
  command "[ -d /opt/cfy/plugins/aws-plugin ] || mkdir -p /opt/cfy/plugins/aws-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/aws-plugin/plugin.yaml"
end