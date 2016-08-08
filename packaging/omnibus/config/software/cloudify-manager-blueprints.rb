name "cloudify-manager-blueprints"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
ENV['TELCO_MODE'] || raise('TELCO_MODE environment variable not set')

default_version ENV['CORE_TAG_NAME']
telco_mode=ENV['TELCO_MODE']

source :git => "https://github.com/cloudify-cosmo/cloudify-manager-blueprints"

build do
  if telco_mode=="true"
    file_names = Dir.glob("../cloudify-manager-blueprints/**/*-blueprint.yaml")
    file_names.each do |file_name|
      text = File.read(file_name)
      new_contents = text.gsub(/  telecom_edition:\n    description: >\n      Set this to true if you want Telecom Edition\n    type: boolean\n    default: false/, "  telecom_edition:\n    description: >\n      Set this to true if you want Telecom Edition\n    type: boolean\n    default: true")

      # print the contents of the file, use:
      puts new_contents

      # write changes to the file, use:
      File.open(file_name, "w") {|file| file.puts new_contents }
    end
  end

  command "cp -r ../cloudify-manager-blueprints /opt/cfy/"
end