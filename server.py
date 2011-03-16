#!/usr/bin/env python

"""
@file server.py
@author Paul Hubbard
@date 6/17/10
@brief TCP glue logic between buildbot and the arduino. Does lots. Docs lacking.
@see http://twistedmatrix.com/documents/current/core/howto/clients.html
"""

from time import time
import logging
import re
import sys
from twisted.web import server, resource
from twisted.protocols.basic import LineReceiver
from twisted.web import client
from twisted.internet import reactor, protocol, task
from twisted.python import usage
import json

# The arduino reads these as bytes and subtracts 'a', so a is zero, etc.
RED = 'zaa'
GREEN = 'aza'
BLUE = 'aaz'
WHITE = 'zzz'
BLACK = 'aaa'

# Global variables
current_color = BLUE
last_time = 0
lastTemp = 0.0
lastRH = 0.0

class ALOptions(usage.Options):
    """
    Command-line parameters for the program. Which arduino (IP), what port to
    serve HTTP on, polling frequency, where to find buildbot, etc.
    """
    optParameters = [
        ['port', 'p', 80, 'TCP port to connect to'],
        ['wsport', 'w', 2000, 'TCP port to run webserver on'],
        ['hostname', 'h', 'ooi-arduino.ucsd.edu', 'hostname or IP to connect to'],
        ['build', 'b', 'amoeba-ioncore-python', 'Prefix for build(s) to monitor'],
        ['bboturl', 'u', 'http://ooici.net:8010', 'Buildbot URL'],
        ['interval', 'i', 30, 'Polling interval, seconds'],
    ]

class indexPage(resource.Resource):
    """
    Class for the web page. Just returns a single page on the root with the
    latest temp and humidity.
    """
    isLeaf = True

    def render_GET(self, request):
        # Want to return raw text, so we can also parse it with Cacti
        # see http://docs.cacti.net/manual:087:3a_advanced_topics.1_data_input_methods#data_input_methods
        ccStr = 'Temp:%f Humidity:%f\n' % (lastTemp, lastRH)
        return ccStr

class ArduinoClient(LineReceiver):
    """
    Main interface to the arduino. When we connect, set the color and trigger
    a read of the latest ADC readings.
    """
    def connectionMade(self):
        global current_color
        logging.info('Connected! Sending color ' + current_color)
        self.transport.write(current_color + '\n')

    def lineReceived(self, line):
        logging.debug('sensor data: "%s"' % line)
        data = line.split()
        self.processData(data)
        self.transport.loseConnection()

    def processData(self, data):
        """
        Convert raw ADC counts into SI units as per datasheets. Could have been
        done on the arduino, but easier to get working here.
        """
        # Skip bad reads
        if len(data) != 2:
            return

        global lastTemp, lastRH

        tempCts = int(data[0])
        rhCts = int(data[1])

        rhVolts = rhCts * 0.0048828125

        # 10mV/degree, 1024 count/5V
        temp = tempCts * 0.48828125
        # RH temp correction is -0.7% per deg C
        rhcf = (-0.7 * (temp - 25.0)) / 100.0

        # Uncorrected humidity
        humidity = (rhVolts * 45.25) - 42.76

        # Add correction factor
        humidity = humidity + (rhcf * humidity)

        lastTemp = temp
        lastRH = humidity

        logging.info('Temp: %f C Relative humidity: %f %%' % (temp, humidity))
        logging.debug('Temp: %f counts: %d RH: %f counts: %d volts: %f' % (temp, tempCts, humidity, rhCts, rhVolts))

class ACFactory(protocol.ClientFactory):
    """
    Factory class for arduino connections.
    """
    protocol = ArduinoClient

    def startedConnecting(self, connector):
        pass

    def clientConnectionFailed(self, connector, reason):
        logging.error('failed connection "%s" ' % reason)

    def clientConnectionLost(self, connector, reason):
        pass

def set_status(new_color):
    global last_time, current_color

    last_time = time()
    current_color = new_color

def decode_buildpage(json_build_page):
    """
    Given a page for a specific build, parse to extract build status
    """
    logging.debug('starting to decode build page')
    dp = json.loads(json_build_page)
    """
    Should get something like
    "text": [
    "build",
    "successful"
    ],
     """
    if dp['text'][1] == 'successful':
        logging.info('Build successful, going green')
        set_status(GREEN)
    else:
        logging.info('Build is "%s", going red' % dp['text'][1])
        set_status(RED)
    

def decode_page(json_page, bbot_url, main_build):
    logging.debug('Starting to decode main json page')
    dp = json.loads(json_page)

    status = dp[main_build]['state']
    if status != 'idle':
        logging.debug('Build state is %s, setting blue' % status)
        # Build in progress
        set_status(BLUE)
        return

    last_buildno = max(dp[main_build]['cachedBuilds'])
    logging.debug('Looking for build #%d' % last_buildno)

    d = client.getPage(bbot_url + '/json/builders/%s/builds/%d' % (main_build, last_buildno))
    d.addCallback(decode_buildpage)

    
def poll_bb_json(bbot_url, main_build):
    """
    Pull the JSON-encoded build status, used to be XMLRPC but that was removed from 0.8.3
    """
    global last_time, current_color

    json_url = bbot_url + '/json/builders/'

    logging.debug('about to check %s' % json_url)
    d = client.getPage(json_url)
    d.addCallback(decode_page, bbot_url, main_build)


def ab_main(o):
    """
    Glue it all together. Parse the command line, setup logging, start the
    timers, connect up website.
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

    bbot_url = o.opts['bboturl']
    main_build = o.opts['build']
    port = o.opts['port']
    wsport = o.opts['wsport']
    host = o.opts['hostname']
    interval = int(o.opts['interval'])

    logging.info('Setting up a looping call to the poller, %d seconds' % interval)
    pt = task.LoopingCall(poll_bb_json, bbot_url, main_build)
    pt.start(interval)

    logging.info('Setting up a looping call for the arduino client')
    ct = task.LoopingCall(reactor.connectTCP, host, port, ACFactory())
    ct.start(interval)

    logging.info('Setting up webserver on port %d' % wsport)

    # HTTP interface
    root = indexPage()
    site = server.Site(root)
    reactor.listenTCP(wsport, site)

    logging.info('Running!')
    reactor.run()

if __name__ == "__main__":
    o = ALOptions()
    try:
        o.parseOptions()
    except usage.UsageError, errortext:
        logging.error('%s %s' % (sys.argv[0], errortext))
        logging.info('Try %s --help for usage details' % sys.argv[0])
        raise SystemExit, 1

    ab_main(o)
