require 'spec_helper'

if os[:family] == 'windows'

  describe package('Cloudify-windows v1.0.0') do
    it { should be_installed }
  end 

  describe file('c:/cloudify') do
    it { should be_directory }
  end

  describe file('c:/cloudify/embedded') do
    it { should be_directory }
  end

  describe file('c:/cloudify/embedded/Scripts') do
    it { should be_directory }
  end

  describe command('c:/cloudify/embedded/Scripts/cfy.exe --help') do
    its(:stdout) { should match(/usage: cfy-script.py \[-h\] \[--version\]/) }
  end

  describe command('c:/cloudify/embedded/Scripts/cfy.exe init') do
    its(:stdout) { should match(/Initialization completed successfully/) }
  end

end
