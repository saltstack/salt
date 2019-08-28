# This file is only used for running the test suite with kitchen-salt.

source 'https://rubygems.org'

gem 'test-kitchen', '~>1.23.3'
gem 'kitchen-salt', :git => 'https://github.com/saltstack/kitchen-salt.git'
gem 'kitchen-sync'
gem 'git'

group :docker do
  gem 'kitchen-docker', :git => 'https://github.com/test-kitchen/kitchen-docker.git'
end

group :windows do
  gem 'winrm', '~>2.0'
#  gem 'winrm-fs', '~>1.3.1'
  gem 'winrm-fs', :git => 'https://github.com/s0undt3ch/winrm-fs.git', :branch => 'hotfix/saltstack-ci'
end

group :ec2 do
  gem 'kitchen-ec2'
end

group :vagrant do
  gem 'vagrant-wrapper'
  gem 'kitchen-vagrant'
end

group :macos do
  gem 'rbnacl', '< 5.0', :require => false
  gem 'rbnacl-libsodium', :require => false
  gem 'bcrypt_pbkdf', '< 2.0', :require => false
  gem 'ffi', '= 1.10.0', :require => false
end
