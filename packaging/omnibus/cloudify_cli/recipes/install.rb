
# reload ohai data
ohai 'reload' do
  action :reload
end

# should only be one of each rpm/deb
pkg_path = Dir.glob("#{node['etc']['passwd']['vagrant']['dir']}/cloudify/pkg/cloudify*rpm")[0] if node['platform_family'] == 'rhel'
pkg_path = Dir.glob("#{node['etc']['passwd']['vagrant']['dir']}/cloudify/pkg/cloudify*deb")[0] if node['platform_family'] == 'debian'
pkg_path = Dir.glob("#{ENV['HOME']}/pkg/cloudify*msi")[0] if node['platform_family'] == 'windows'

if node['platform_family'].include?("debian")
  # source not supported by apt_package so must override with dpkg_package
  dpkg_package 'cloudify' do
    action :install
    source pkg_path
  end
else
  package 'cloudify' do
    action :install
    source pkg_path
  end
end
