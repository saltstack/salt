'''
EXPERIMENTAL, subject to change
----------------------------------
The backend for the s3 service.

Example configuration options in master file:

s3_key_id: XXXXXXXXXXXXXXX
s3_server_access_key: XXXXXXXXXXXXXXX
s3_buckets:
  env:
    - bucket1
    - bucket2    
    

:depends: git-python Python module
'''

# Import python libs
import os
import hashlib
import logging

# Import salt libs
import salt.fileserver
import salt.utils
import salt.utils.s3 as s3
import salt.modules


log = logging.getLogger(__name__)

def init():
    '''
        Fetches data for the rest of the module to work off
    '''
    fetch_result_set()   

def find_file(path, env='base', **kwargs):
    '''
    Looks through the buckets to find the first matching file and formats it 
    '''

    fnd = {'bucket':   '',
           'path'  :   '',
           'md5'   :   ''}

    if env not in __opts__['s3_buckets']:
        return fnd    
    ret = []
    resultset = get_result_set()
    for path,val in resultset[env].items():
        fileData = filter(lambda key: key.has_key("Key"), val)
        filePaths = map(lambda key: key["Key"], fileData)
        filesOnly = filter(lambda key: key.endswith('/') == False, filePaths)
        filesWithBucket = map(lambda key: path+"//"+key, filesOnly)
        ret += filesWithBucket

    fnd['bucket'] = filter(lambda key: key.split('//')[0] == path , ret)[0].split('//')[0]
    fnd['path']   = filter(lambda key: key.split('//')[0] == path , ret)[0].split('//')[1]
    fnd['rel'] = fnd['path']
    bucket = fnd["bucket"]
    path = fnd["path"]
    fileData = filter(lambda key: key.has_key("Key"),  resultset[env][bucket])
    item =  filter(lambda key: key["Key"] == path , fileData)[0]
    fnd['md5'] = item["Key"]

    return fnd        
def envs():
    '''
    Return the file server environments
    '''
    return __opts__['s3_buckets'].keys()


def serve_file(load, fnd):
    s3_key_id =  __opts__['s3_key_id'] if __opts__['s3_key_id'] else None 
    s3_server_access_key = __opts__['s3_server_access_key'] if __opts__['s3_server_access_key'] else None 

    env = load["env"]
    bucket = fnd["bucket"]
    path = fnd["path"]

    abspath = os.path.join( __opts__['cachedir'],'s3cache',bucket,fnd["path"])
    absdirectory = abspath[0:abspath.rfind("/")]
    ret = {}


    if not os.path.exists(absdirectory):
        os.makedirs(absdirectory)
    if os.path.isfile(abspath):
            with salt.utils.fopen(abspath, 'rb') as fp_:
                diskmd5 = hashlib.md5(fp_.read()).hexdigest()
                if diskmd5 == fnd["md5"]:
                    ret['dest'] = bucket+"//"+path
                    ret['data'] = fp_.read()
    else:
        with salt.utils.fopen(abspath, 'w') as fp_:
            fetchedFile = s3.query(s3_server_access_key,s3_key_id,bucket=bucket,path=path,return_bin=True)
            fp_.write(fetchedFile)


    gzip = load.get('gzip', None)
    with salt.utils.fopen(abspath, 'rb') as fp_:
        fp_.seek(load['loc'])
        data = fp_.read(__opts__['file_buffer_size'])
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret['gzip'] = gzip
        ret['data'] = data
        ret['dest'] = bucket+"//"+path
        return ret

def file_hash(load, fnd):
    '''
        Provides Salt with 
    '''
    ret = {}
    resultset = get_result_set()
    env = load["env"]
    bucket = fnd["bucket"]
    path = fnd["path"]

    fileData = filter(lambda key: key.has_key("Key"),  resultset[env][bucket])
    item =  filter(lambda key: key["Key"] == path , fileData)[0]
    ret['hsum'] = item["ETag"]
    ret['hash_type'] = "md5"
    return ret 

def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''    
    ret = []
    resultset = get_result_set()
    env = load['env']
    for path,val in resultset[env].items():
        fileData = filter(lambda key: key.has_key("Key"), val)
        filePaths = map(lambda key: key["Key"], fileData)
        filesOnly = filter(lambda key: key.endswith('/') == False, filePaths)
        filesWithBucket = map(lambda key: path+"//"+key, filesOnly)
        ret += filesWithBucket
    return ret

def fetch_result_set():
    '''
    Connects to S3 and downloads metadata about each file in all 
    buckets specified within and environment and saves them to disk
    '''    

    s3_key_id =  __opts__['s3_key_id'] if __opts__['s3_key_id'] else None 
    s3_server_access_key = __opts__['s3_server_access_key'] if __opts__['s3_server_access_key'] else None 

    resultset = {}
    for env,buckets in __opts__['s3_buckets'].items():
        _buckets = {}
        for val in buckets:
            try:
                _buckets[val] = s3.query(s3_server_access_key,s3_key_id,bucket=val,return_bin=False)
            except TypeError:
                log.error('There was an error accessing the ' + path + " Bucket")
        resultset[env] = _buckets

    abspath = os.path.join( __opts__['cachedir'],'s3cache',"apiReturn")
    absdirectory = abspath[0:abspath.rfind("/")]
    if not os.path.exists(absdirectory):
        os.makedirs(absdirectory)
    if os.path.isfile(abspath):
        os.remove(abspath)
    with salt.utils.fopen(abspath, 'w') as fp_:
        fp_.write(str(resultset))

def get_result_set():
    '''
    Returns cached result set from S3 Api Call in fetch_result_set()
    '''    
    abspath = os.path.join( __opts__['cachedir'],'s3cache',"apiReturn")
    with salt.utils.fopen(abspath, 'rb') as fp_:
        data = fp_.read()
        return eval(data)
   
