#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#

name "cloudify"
maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

override :cacerts, version: '2015.10.28', source: { md5: '38cd779c9429ab6e2e5ae3437b763238' }
override :pip, version: '7.1.2', source: { md5: '3823d2343d9f3aaab21cf9c917710196' }
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.8', source: { md5: '44d667c142d7cda120332623eab69f40'}
override :openssl, version: '1.0.1k'

# Defaults to C:/cloudify on Windows
# and /opt/cfy on all other platforms
install_dir "#{default_root}/cfy"

build_version Omnibus::BuildVersion.semver

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

