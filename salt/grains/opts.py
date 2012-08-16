def opts():
  '''
  Return the minion configuration settings
  '''
  if __opts__.get('grain_opts', False) or __pillar__.get('grain_opts', False):
    return __opts__
  return {}
