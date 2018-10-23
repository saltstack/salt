import requests


def test_server(host_ip, http_port):
    '''
    Test that wordpress was setup on the minion correctly and returns a 200 after being installed
    '''
    resp = requests.get('http://{0}:{1}'.format(host_ip, http_port), headers={'Host': 'blog.manfred.io'})
    assert resp.status_code == 200
