# run by file.managed with template=py

def run():
    # context is passed through file.managed
    # and gets the value through jinja templating
    return context['output']
