name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
premium=ENV['PREMIUM']
premium_folder=ENV['PREMIUM_FOLDER']

#default_version ENV['CORE_TAG_NAME']
default_version 'temp'

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"
puts "premium_folder=#{premium_folder}"

build do
  command "cp -r ../cloudify-manager-blueprints /opt/cfy/"

  if premium == "true"
      str_to_replace="s|cloudify-manager-resources|#{premium_folder}\/cloudify-premium-manager-resources|g"
      cmd="sed -i \"#{str_to_replace}\" /opt/cfy/cloudify-manager-blueprints/inputs/manager-inputs.yaml /opt/cfy/cloudify-manager-blueprints/*-inputs.yaml"
      command cmd
  end
end