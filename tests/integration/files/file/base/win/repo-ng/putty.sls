# just 32-bit x86 installer available
putty:
  '0.69.0.0':
    full_name:  'PuTTY release 0.69 (64-bit)'
    installer: 'https://the.earth.li/~sgtatham/putty/0.69/w64/putty-64bit-0.69-installer.msi'
    uninstaller: 'https://the.earth.li/~sgtatham/putty/0.69/w64/putty-64bit-0.69-installer.msi'
    install_flags: ' /qn '
    uninstall_flags: ' /qn '
    msiexec: True
    locale: en_US
    reboot: False
