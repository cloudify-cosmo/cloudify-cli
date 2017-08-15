name "cloudify-manager-blueprints"

ENV['CORE_BRANCH'] || raise('CORE_BRANCH environment variable not set')
default_version ENV['CORE_BRANCH']
manager_single_tar_url=ENV['SINGLE_TAR_URL']

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do
   command "cp -r ../cloudify-manager-blueprints /opt/cfy/"

   str='!b;'
   spaces='\ \ \ \ '
   str_to_replace="/manager_resources_package:/#{str}n;n;n;c#{spaces}default:  #{manager_single_tar_url}"
   if osx?
     cmd= <<eos
            sed -i '' "/manager_resources_package:/,/manager_resources_package_checksum_file/ {\
            s|default.*|\
            default: '#{manager_single_tar_url}'|
            }
            " /opt/cfy/cloudify-manager-blueprints/inputs/manager-inputs.yaml
eos
   else
     cmd="sed -i \"#{str_to_replace}\" /opt/cfy/cloudify-manager-blueprints/inputs/manager-inputs.yaml"
   end

   command cmd

   str_to_replace="s|.*#manager_resources_package:.*|#manager_resources_package: #{manager_single_tar_url}|g"
   if osx?
     cmd="sed -i '' '#{str_to_replace}\' /opt/cfy/cloudify-manager-blueprints/*-inputs.yaml"
   else
     cmd="sed -i \"#{str_to_replace}\" /opt/cfy/cloudify-manager-blueprints/*-inputs.yaml"
   end

   command cmd

end