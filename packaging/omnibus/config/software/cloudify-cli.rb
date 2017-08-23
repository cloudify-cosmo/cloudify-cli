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

  dependency "pip"


source git: "https://github.com/cloudify-cosmo/cloudify-cli"

build do

    command "curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-dev/install--upgrade/scripts/clap -o ./clap && chmod +x ./clap"
    #command ["#{install_dir}/embedded/bin/virtualenv", "env"]
    #command "source env"
    command ["#{install_dir}/embedded/bin/pip", "install", "sh", "argh", "colorama"]
    command "export CLAP_REPO_BASE=./dev/repos"
    command "export REPOS_BASE_GITHUB_URL=https://github.com/cloudify-cosmo/{0}.git"
    command "git reset --hard HEAD"

    # previous patch gets cached
    patch source: "cloudify_cli.patch"

    command "./clap setup -r ./build-requirements.txt -b #{branch} -d"

    erb :dest => "#{install_dir}/bin/cfy",
      :source => "cfy_wrapper.erb",
      :mode => 0755,
      :vars => { :install_dir => install_dir }
end
