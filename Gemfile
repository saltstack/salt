source "https://rubygems.org"

gem "test-kitchen"
gem "kitchen-salt", :git => 'https://github.com/gtmanfred/kitchen-salt.git'
gem 'git'

group :docker do
  gem 'kitchen-docker', :git => 'https://github.com/test-kitchen/kitchen-docker.git'
end

group :opennebula do
  gem 'kitchen-opennebula', :git => 'https://github.com/gtmanfred/kitchen-opennebula.git'
  gem 'xmlrpc'
end

group :windows do
  gem 'vagrant-wrapper'
  gem 'kitchen-vagrant'
  gem 'winrm', '~>2.0'
  gem 'winrm-fs', '~>1.0'
end
