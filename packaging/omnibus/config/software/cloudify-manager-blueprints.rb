name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
default_version ENV['CORE_TAG_NAME']
manager_single_tar_url=ENV['SINGLE_TAR_URL']

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do
   command "cp -r ../cloudify-manager-blueprints /opt/cfy/"

   str_to_replace="s|default:.*cloudify-manager-resources.*|  default: #{manager_single_tar_url}|g"
   cmd="sed -i \"#{str_to_replace}\" /opt/cfy/cloudify-manager-blueprints/inputs/manager-inputs.yaml /opt/cfy/cloudify-manager-blueprints/*-inputs.yaml"
   command cmd
end