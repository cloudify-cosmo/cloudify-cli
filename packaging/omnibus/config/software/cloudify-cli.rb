#
# Copyright 2015 YOUR NAME
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# These options are required for all software definitions
name "cloudify-cli"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
default_version ENV['CORE_TAG_NAME']

ENV['GITHUB_USERNAME'] || raise('GITHUB_USERNAME environment variable not set (required for private repo)')
ENV['GITHUB_PASSWORD'] || raise('GITHUB_PASSWORD environment variable not set (required for private repo)')
github_username=ENV['GITHUB_USERNAME']
github_password=ENV['GITHUB_PASSWORD']

dependency "python"
if ! windows?
  dependency "pip"
end

source git: "https://github.com/cloudify-cosmo/cloudify-cli"

build do
  if windows?
    command "git reset --hard HEAD"
    command "#{install_dir}/embedded/Scripts/pip.exe install --ignore-installed --build=#{project_dir} . --requirement dev-requirements.txt"
  else
    command "git reset --hard HEAD"  # previous patch gets cached
    patch source: "cloudify_cli.patch"

    command ["#{install_dir}/embedded/bin/pip",
             "install", "-I", "--build=#{project_dir}",
             ".",
             "-r", "dev-requirements.txt"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/aws-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-aws-plugin/archive/1.4.1.zip"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/openstack-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-openstack-plugin/archive/1.4.zip"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/fabric-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-fabric-plugin/archive/1.4.2.zip"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/script-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/1.4.zip"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/vsphere-plugin", ".", "https://#{github_username}:#{github_password}@github.com/cloudify-cosmo/cloudify-vsphere-plugin/archive/2.0.1.zip"]

    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/vcloud-plugin", ".", "https://github.com/cloudify-cosmo/tosca-vcloud-plugin/archive/1.3.1.zip"]

    erb :dest => "#{install_dir}/bin/cfy",
      :source => "cfy_wrapper.erb",
      :mode => 0755,
      :vars => { :install_dir => install_dir }
  end
end
