#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#


ENV['TELCO_MODE'] || raise('TELCO_MODE environment variable not set')
telco_mode=ENV['TELCO_MODE']
puts "telco_mode = #{telco_mode}"

if telco_mode=="true"
    name "cloudify-telco"
else
    name "cloudify"
end

maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

override :cacerts, version: '2015.10.28', source: { md5: '782dcde8f5d53b1b9e888fdf113c42b9' }
override :pip, version: '7.1.2', source: { md5: '3823d2343d9f3aaab21cf9c917710196' }
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.8', source: { md5: '44d667c142d7cda120332623eab69f40' , url: 'http://zlib.net/current/zlib-1.2.8.tar.gz'}


# Defaults to C:/cloudify on Windows
# and /opt/cfy on all other platforms
install_dir "#{default_root}/cfy"

build_version Omnibus::BuildVersion.semver

ENV['BUILD'] || raise('BUILD environment variable not set')
build_iteration ENV['BUILD']

# Creates required build directories
dependency "preparation"
dependency "cloudify-manager-blueprints"
dependency "cloudify-manager"
dependency "script-plugin"
dependency "aws-plugin"
dependency "fabric-plugin"
dependency "openstack-plugin"
dependency "diamond-plugin"
dependency "tosca-vcloud-plugin"
dependency "vsphere-plugin"

# Updates telecom_edition to 'true' in all blueprints, according to env var - not working according to Nirc the simple blueprint will move the cloudify-cli repo
#if telco_mode=="true"
#  puts "Telco mode - changing telecom_edition to 'true'"
#  Dir["/opt/cfy/cloudify-manager-blueprints/*"]
#  file_names = Dir.glob("/opt/cloudify-manager-blueprints/*-blueprint.yaml")
  #file_names = ["aws-ec2-manager-blueprint.yaml", "azure-manager-blueprint.yaml", "vcloud-manager-blueprint.yaml", "simple-manager-blueprint.yaml", "openstack-manager-blueprint.yaml", "vsphere-manager-blueprint.yaml"]
#  puts "file_names = #{file_names}"

#  file_names.each do |file_name|
#    puts "file_name = #{file_name}"
#    text = File.read(file_name)
#    new_contents = text.gsub(/  telecom_edition:\n    description: >\n      Set this to true if you want Telecom Edition\n    type: boolean\n    default: false/, "  telecom_edition:\n    description: >\n      Set this to true if you want Telecom Edition\n    type: boolean\n    default: true")
#    # print the contents of the file, use:
#    puts "new_contents = #{new_contents}"
    # write changes to the file, use:
#    File.open(file_name, "w") {|file| file.puts new_contents }
#  end
#end

# cloudify dependencies/components
dependency "python"
dependency "pip"
dependency "cloudify-cli"

# Version manifest file
dependency "version-manifest"

exclude "**/.git"
exclude "**/bundler/git"

