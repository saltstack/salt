try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def external_ip():
    '''
    Return the external IP address reported by ipecho.net
    '''

    if not HAS_REQUESTS:
        return {}

    try:
        r = requests.get('http://ipecho.net/plain')
        ip = r.content
    except Exception:
        ip = []
    return {'external_ip': ip}
