Vagrant.configure("2") do |config|

  config.vm.provider "virtualbox" do |provider|
    provider.gui = false
    if ENV["CI"]
      provider.memory = 8192
      provider.cpus = 2
    else
      provider.memory = 4096
      provider.cpus = 2
    end
  end

  config.vm.synced_folder ".", "/vagrant/",
    type: "rsync",
    rsync__args: [
      "--verbose",
      "--archive",
      "--delete",
      "-H", # Human readable
      "--stats"
    ],
    rsync__exclude: [
      ".nox/",
      ".pytest_cache/",
      "artifacts/",
    ],
    rsync_verbose: true

  config.vm.define "debian-10" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/debian-10"
    vmconfig.vm.box_version = "20220818.1810"
  end

  config.vm.define "debian-11" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/debian-11"
    vmconfig.vm.box_version = "20220818.1804"
  end

  config.vm.define "centos-stream-8" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/centos-stream-8"
    vmconfig.vm.box_version = "20220816.1514"
  end

  config.vm.define "fedora-35" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/fedora-35"
    vmconfig.vm.box_version = "20220818.1806"
  end

  config.vm.define "fedora-36" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/fedora-36"
    vmconfig.vm.box_version = "20220818.1822"
  end

end
