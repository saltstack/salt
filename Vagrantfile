require 'json'
boxes_json_file = File.read('Vagrantfile.boxes.json')
vagrant_boxes = JSON.parse(boxes_json_file)

Vagrant.configure("2") do |config|

  config.vm.provider "virtualbox" do |provider|
    provider.gui = false
    provider.linked_clone = true if Gem::Version.new(Vagrant::VERSION) >= Gem::Version.new('1.8.0')
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

  [
    "debian-10",
    "debian-11",
    "centos-stream-8",
    "fedora-35",
    "fedora-36"
  ].each do |vmname|
    config.vm.define vmname do |vmconfig|
      vmconfig.vm.box = ENV["box_name"] || vagrant_boxes[vmname]["box_name"]
      vmconfig.vm.box_version = ENV["box_version"] || vagrant_boxes[vmname]["box_version"]
    end
  end

end
