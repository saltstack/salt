Vagrant.configure("2") do |config|
  #config.vagrant.plugins = ["virtualbox"]
  config.vm.provider "virtualbox" do |provider|
    provider.gui = false
    provider.memory = 8096
    provider.cpus = 2
  end

  config.vm.synced_folder ".", "/vagrant", type: "rsync", rsync__args: [
    "--verbose",
    "--archive",
    "--delete",
    "-z",
    "--copy-links",
    "--perms",
    "-H",
    "--stats"
  ]

  config.vm.define "debian-10" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/debian-10"
    vmconfig.vm.box_version = "20220815.1836"
  end

  config.vm.define "debian-11" do |vmconfig|
    vmconfig.vm.box = "salt-project-ci/debian-11"
    vmconfig.vm.box_version = "20220815.1816"
  end

end
