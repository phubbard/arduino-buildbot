#!/usr/bin/env python

"""
@file pachube.py
@author Paul Hubbard
@date April 8 2011
@brief Pachube data source that reads from the web interface and pushes to Pachube.
@note Experimental code, if this works I'll roll it into the main python server
"""

import httplib
import logging as log
from urllib2 import urlopen
import time


DATA_URL = 'http://ooici.net:2000/'
UPDATE_DELAY = 60.0; # seconds between polls

API_KEY = '235cafb47b49596a9c54c9a5fa249ea5da2c43d70d6d2b24b21da95a91371397'
API_URL = '/v2/feeds/22374.csv'

def grab_data(data_url=DATA_URL):
    fh = urlopen(data_url)
    page=fh.read().strip()
    log.debug(page)

    # Data looks like this
    # Temp:28.320312 Humidity:17.150503
    f = page.split(' ')
    tdata = f[0].split(':')
    temp = float(tdata[1])

    rhdata = f[1].split(':')
    rh = float(rhdata[1])
    log.info('Temp: %f RH: %f' % (temp, rh))
    return temp,rh

def update_byhand(temp, rh):
    conn = httplib.HTTPConnection('api.pachube.com')

    data_str = '0,%f\n1,%f\n\n' % (temp, rh)
    conn.request('PUT', API_URL, data_str, {'X-PachubeApiKey': API_KEY})
    resp = conn.getresponse()
    if resp.status != 200:
        raise Exception(resp.reason)
    log.debug('Updated OK')
    conn.close()

def main():
    while True:
        temp, rh = grab_data()
        update_byhand(temp, rh)
        time.sleep(UPDATE_DELAY)

if __name__ == '__main__':
    log.basicConfig(level=log.INFO, format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

    main()