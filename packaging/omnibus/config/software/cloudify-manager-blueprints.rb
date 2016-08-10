name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')

default_version "3.4.0.1-telco"

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do
  command "cp -r ../cloudify-manager-blueprints /opt/cfy/"
end