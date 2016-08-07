name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')

default_version ENV['CORE_TAG_NAME']

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do

  command "cp -r ../cloudify-manager-blueprints /opt/cfy/"

end