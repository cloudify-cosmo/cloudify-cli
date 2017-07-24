#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#

name "cloudify"
maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

pip_version = '9.0.1'

ENV['VERSION'] || raise('VERSION environment variable not set')
ENV['PRERELEASE'] || raise('PRERELEASE environment variable not set')
cloudify_ver=ENV['VERSION']
cloudify_pre=ENV['PRERELEASE']

override :cacerts, version: '2015.10.28', source: { md5: '9d8c2e9a93881cdf1f2a7fc3d01a6318' }
override :pip, version: pip_version, source: {
  url: "https://files.pythonhosted.org/packages/source/p/pip/pip-#{pip_version}.tar.gz",
  md5: '35f01da33009719497f01a4ba69d63c9'
}
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }
override :zlib, version: '1.2.8', source: { md5: '44d667c142d7cda120332623eab69f40'}

# Defaults to C:/cloudify on Windows
# and /opt/cfy on all other platforms
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
