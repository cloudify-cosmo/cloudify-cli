name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
ENV['TELCO_MODE'] || raise('TELCO_MODE environment variable not set')

telco_mode=ENV['TELCO_MODE']
if telco_mode=="true"
    default_version "3.4.1-telco"
else
    default_version "3.4.1"
end

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do
  command "cp -r ../cloudify-manager-blueprints /opt/cfy/"
end