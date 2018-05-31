# This file is only used for running the test suite with kitchen-salt.

source 'https://rubygems.org'

gem 'test-kitchen', '~>1.21'
gem 'kitchen-salt', '~>0.2'
gem 'kitchen-sync'
gem 'git'

group :docker do
  gem 'kitchen-docker', :git => 'https://github.com/test-kitchen/kitchen-docker.git'
end

group :opennebula do
  gem 'kitchen-opennebula', '>=0.2.3'
  gem 'xmlrpc'
end

group :windows do
  gem 'vagrant-wrapper'
  gem 'kitchen-vagrant'
  gem 'winrm', '~>2.0'
  gem 'winrm-fs', :git => 'https://github.com/WinRb/winrm-fs.git'
end

group :ec2 do
  gem 'kitchen-ec2'
end
