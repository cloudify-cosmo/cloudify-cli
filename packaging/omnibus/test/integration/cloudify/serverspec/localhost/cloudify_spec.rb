require 'spec_helper'

if ['debian', 'centos', 'redhat', 'ubuntu'].include?(os[:family]) 

  describe package('cloudify') do
    it { should be_installed }
  end 

  describe file('/opt/cloudify') do
    it { should be_directory }
    it { should be_readable }
  end

  describe file('/opt/cloudify/bin') do
    it { should be_directory }
    it { should be_readable }
  end

  describe file('/opt/cloudify/embedded') do
    it { should be_directory }
    it { should be_readable }
  end

  describe file('/usr/bin/cfy') do
    it { should be_executable }
  end

  describe file('/opt/cloudify/bin/cfy') do
    it { should be_executable }
  end

  describe command('/usr/bin/cfy --help') do
    its(:stdout) { should match(/usage: cfy \[-h\] \[--version\]/) }
  end

  describe command('/usr/bin/cfy init') do
    its(:stdout) { should match(/Initialization completed successfully/) }
  end

end
