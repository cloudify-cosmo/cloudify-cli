name "cloudify-manager"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')

default_version "3.4.0.2"

source :git => "https://github.com/cloudify-cosmo/cloudify-manager"

build do
  command "[ -d /opt/cfy/types/ ] || mkdir -p /opt/cfy/types/"
  command "cp  ../cloudify-manager/resources/rest-service/cloudify/types/types.yaml /opt/cfy/types/types.yaml"
end