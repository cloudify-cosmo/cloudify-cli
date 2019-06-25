#########
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

name "cloudify-windows"
maintainer "Cloudify"
homepage "https://cloudify.co"

build_version '1.0.0'
package_name "cloudify"
install_dir "#{default_root}/#{package_name}"

dependency "preparation"
# cloudify-windows dependencies/components
dependency "python"
dependency "cloudify-cli"

project_location_dir = "cloudify"
package :msi do
  upgrade_code "34ece924-9cfd-404d-bbe3-abce7d4ba146"
  wix_candle_extension 'WixUtilExtension'
end

# Version manifest file
dependency "version-manifest"

exclude "**/.git"
exclude "**/bundler/git"
