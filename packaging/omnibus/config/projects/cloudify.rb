#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#

name "cloudify"
maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

override :cacerts, version: '2015.10.28', source: { md5: '1fc922c991c9d8e7c4bfb3e2c64df3fa' }
override :pip, version: '7.1.2', source: { md5: '3823d2343d9f3aaab21cf9c917710196' }
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.8', source: { url: 'http://repository.cloudifysource.org/org/cloudify3/components/zlib-1.2.8.tar.gz'}

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

# cloudify dependencies/components
dependency "python"
dependency "pip"
dependency "cloudify-cli"

# Version manifest file
dependency "version-manifest"

exclude "**/.git"
exclude "**/bundler/git"

