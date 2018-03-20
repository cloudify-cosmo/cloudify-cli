name "vsphere-plugin"

plugin_version = "vsphere-plugin/2.4.0"
default_version plugin_version.sub! "vsphere-plugin/", ""

ENV['GITHUB_USERNAME'] || raise('GITHUB_USERNAME environment variable not set (required for private repo)')
ENV['GITHUB_PASSWORD'] || raise('GITHUB_PASSWORD environment variable not set (required for private repo)')

github_username=ENV['GITHUB_USERNAME']
github_password=ENV['GITHUB_PASSWORD']

source :git => "https://#{github_username}:#{github_password}@github.com/cloudify-cosmo/cloudify-vsphere-plugin"

build do
  command "[ -d /opt/cfy/plugins/cloudify-vsphere-plugin ] || mkdir -p /opt/cfy/plugins/cloudify-vsphere-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/cloudify-vsphere-plugin/plugin.yaml"
end

whitelist_file /.*/