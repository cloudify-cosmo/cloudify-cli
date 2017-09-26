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

# override :cacerts, version: '2017-06-07', source: { md5: 'cb530d737c8f2d1023797cf0587b4e05' }
override :pip, version: '7.1.2', source: { md5: '3823d2343d9f3aaab21cf9c917710196' }
override :setuptools, version: '0.9.8'
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
