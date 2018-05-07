name "cloudify-manager"

ENV['CORE_BRANCH'] || raise('CORE_BRANCH environment variable not set')


default_version ENV['CORE_BRANCH']

source :git => "https://github.com/cloudify-cosmo/cloudify-manager"

build do
  command "[ -d /opt/cfy/types/ ] || mkdir -p /opt/cfy/types/"
  command "cp  ../cloudify-manager/resources/rest-service/cloudify/types/types.yaml /opt/cfy/types/types.yaml"
end