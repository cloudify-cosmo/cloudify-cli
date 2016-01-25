#
# Copyright 2015 Gigaspaces
#
# All Rights Reserved.
#

name "cloudify-windows"
maintainer "Gigaspaces"
homepage "http://getcloudify.org"

build_version '1.0.0'
build_iteration 1
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
