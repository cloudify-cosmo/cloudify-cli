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

branch=ENV['CORE_BRANCH']
#{branch} || raise('CORE_BRANCH environment variable not set')
default_version 'clap'
#default_version #{branch}

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

  command "curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-dev/install--upgrade/scripts/clap -o ./clap && chmod +x ./clap"
  command "pip install sh argh colorama"
  command "export CLAP_REPO_BASE=./dev/repos"
  command "export REPOS_BASE_GITHUB_URL=https://github.com/cloudify-cosmo/{0}.git"

  if windows?
    command "git reset --hard HEAD"
    #command "#{install_dir}/embedded/Scripts/pip.exe install --ignore-installed --build=#{project_dir} . --requirement dev-requirements.txt"
    command "./clap setup -r ./build-requirements.txt -b #{branch} -d"
  else
    command "git reset --hard HEAD"  # previous patch gets cached
    patch source: "cloudify_cli.patch"

    #command ["#{install_dir}/embedded/bin/pip",
    #         "install", "-I", "--build=#{project_dir}",
    #         ".",
    #         "-r", "dev-requirements.txt"]

    command "./clap setup -r ./build-requirements.txt -b #{branch}"

    #command ["#{install_dir}/embedded/bin/pip",
    #         "install", "--build=#{project_dir}/fabric-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-fabric-plugin/archive/1.5.1.zip"]


    #command ["#{install_dir}/embedded/bin/pip",
    #         "install", "--build=#{project_dir}/script-plugin", ".", "https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/1.5.1.zip"]


    erb :dest => "#{install_dir}/bin/cfy",
      :source => "cfy_wrapper.erb",
      :mode => 0755,
      :vars => { :install_dir => install_dir }
  end
end
