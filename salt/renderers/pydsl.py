import imp


def render(template, env='', sls='', tmplpath=None, **kws):
    mod = imp.new_module(sls)
    dsl_sls = __salt__['pydsl.sls'](sls)
    mod.__dict__.update(
        include=dsl_sls.include,
        extend=dsl_sls.extend,
        state=dsl_sls.state,
        __salt__=__salt__,
        __grains__=__grains__,
        __opts__=__opts__,
        __pillar__=__pillar__,
        env=env,
        sls=sls,
        tmplpath=tmplpath,
        **kws)
    exec template.read() in mod.__dict__
    return dsl_sls.to_highstate()
    
