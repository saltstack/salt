ping -c 2 {{ pillar['myhost'] }}:
  cmd.run
