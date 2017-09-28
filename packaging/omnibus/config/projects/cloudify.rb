#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#

name "cloudify"
maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

ENV['VERSION'] || raise('VERSION environment variable not set')
ENV['PRERELEASE'] || raise('PRERELEASE environment variable not set')
cloudify_ver=ENV['VERSION']
cloudify_pre=ENV['PRERELEASE']

override :cacerts, version: '2017-06-07', source: { url: 'https://curl.haxx.se/ca/cacert-2017-06-07.pem', sha256: 'e78c8ab7b4432bd466e64bb942d988f6c0ac91cd785017e465bdc96d42fe9dd0' }
override :pip, version: '7.1.2', source: { md5: '3823d2343d9f3aaab21cf9c917710196' }
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.8'

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
dependency "cloudify-manager-blueprints"
dependency "cloudify-manager"
dependency "script-plugin"
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
