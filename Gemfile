# This file is only used for running the test suite with kitchen-salt.

source 'https://rubygems.org'

# Point this back at the test-kitchen package after 1.23.3 is relased
gem 'test-kitchen', :git => 'https://github.com/dwoz/test-kitchen.git', :branch => 'winrm_opts'
gem 'kitchen-salt', '~>0.2'
gem 'kitchen-sync'
gem 'git'

group :docker do
  gem 'kitchen-docker', :git => 'https://github.com/test-kitchen/kitchen-docker.git'
end

group :windows do
  gem 'winrm', '~>2.0'
  gem 'winrm-fs', '~>1.3.1' 
end

group :ec2 do
  gem 'kitchen-ec2'
end

group :vagrant do
  gem 'vagrant-wrapper'
  gem 'kitchen-vagrant'
end
