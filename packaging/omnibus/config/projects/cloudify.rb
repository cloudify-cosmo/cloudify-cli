#
# Copyright (c) 2015-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

name "cloudify"
maintainer "cloudify"
homepage "https://cloudify.co/"

ENV['VERSION'] || raise('VERSION environment variable not set')
ENV['PRERELEASE'] || raise('PRERELEASE environment variable not set')
cloudify_ver=ENV['VERSION']
cloudify_pre=ENV['PRERELEASE']

override :pip, version: '9.0.1'
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.11', source: { sha256: 'c3e5e9fdd5004dcb542feda5ee4f0ff0744628baf8ed2dd5d66f8ca1197cb1a1', url: 'https://zlib.net/zlib-1.2.11.tar.gz'}

# Defaults to C:/cloudify on Windows
# and /opt/cfy on all other platforms
if osx?
  default_root = "/usr/local/opt/"
else
  default_root = "/opt/"
end

install_dir "#{default_root}/cfy"

build_version "#{cloudify_ver}-#{cloudify_pre}"

# Creates required build directories
dependency "preparation"
dependency "cloudify-manager"
dependency "aws-plugin"
dependency "fabric-plugin"
dependency "openstack-plugin"
dependency "diamond-plugin"
dependency "vsphere-plugin"

# cloudify dependencies/components
dependency "python"
dependency "pip"
dependency "cloudify-cli"

# Version manifest file
dependency "version-manifest"

exclude "**/.git"
exclude "**/bundler/git"
