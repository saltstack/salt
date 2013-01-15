import imp


def render(template, env='', sls='', tmplpath=None, **kws):
    mod = imp.new_module(sls)
    # Note: mod object is transient. It's existence only lasts as long as
    #       the lowstate data structure that the highstate in the sls file
    #       is compiled to.

    mod.__name__ = sls

    # to workaround state.py's use of copy.deepcopy(chunck)
    mod.__deepcopy__ = lambda x: mod

    dsl_sls = __salt__['pydsl.sls'](sls)
    mod.__dict__.update(
        __pydsl__=dsl_sls,
        include=dsl_sls.include,
        extend=dsl_sls.extend,
        state=dsl_sls.state,
        __salt__=__salt__,
        __grains__=__grains__,
        __opts__=__opts__,
        __pillar__=__pillar__,
        __env__=env,
        __sls__=sls,
        __file__=tmplpath,
        **kws)
    exec template.read() in mod.__dict__
    return dsl_sls.to_highstate(mod)
    
