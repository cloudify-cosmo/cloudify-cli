name "vsphere-plugin"

plugin_version = "vsphere-plugin/2.4.0"
default_version plugin_version.sub! "vsphere-plugin/", ""

ENV['GITHUB_USERNAME'] || raise('GITHUB_USERNAME environment variable not set (required for private repo)')
ENV['GITHUB_TOKEN'] || raise('GITHUB_TOKEN environment variable not set (required for private repo)')

github_username=ENV['GITHUB_USERNAME']
github_token=ENV['GITHUB_TOKEN']

source :git => "https://#{github_username}:#{github_token}@github.com/cloudify-cosmo/cloudify-vsphere-plugin"

build do
  command "[ -d /opt/cfy/plugins/cloudify-vsphere-plugin ] || mkdir -p /opt/cfy/plugins/cloudify-vsphere-plugin"
  command "cp plugin.yaml /opt/cfy/plugins/cloudify-vsphere-plugin/plugin.yaml"
end

whitelist_file /.*/