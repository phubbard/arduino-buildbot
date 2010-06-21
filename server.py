#!/usr/bin/env python

"""
@file server.py
@author Paul Hubbard
@date 6/17/10
@brief TCP glue logic between buildbot and the arduino. Does lots. Docs lacking.
@see http://twistedmatrix.com/documents/current/core/howto/clients.html
"""

from time import time
from xmlrpclib import ServerProxy
import logging
import re
import sys
from twisted.web import server, resource
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor, protocol, task
from twisted.python import usage

"""
The arduino reads these as bytes and subtracts 'a', so a is zero, etc.
Crude but simple.
"""
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
        ['build', 'b', 'lcaarch', 'Prefix for build(s) to monitor'],
        ['bboturl', 'u', 'http://ooici.net:8010/xmlrpc', 'Buildbot XML-RPC URL'],
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
        logging.info('sensor data: "%s"' % line)
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

class ACFactory(protocol.ServerFactory):
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

def poll_buildbot(bbot_url, main_build):
    """
    Hit the XML-RPC service in buildbot to query the last few builds and
    look for the one(s) we're monitoring.
    """
    global last_time, current_color
    proxy = ServerProxy(bbot_url)

    # First run?
    if last_time == 0:
        last_time = time() - 3600;

    logging.debug('Checking for builds...')
    now = time()
    builds = proxy.getAllBuildsInInterval(last_time, now)
    if len(builds) > 0:
        logging.debug('%d total build(s) found' % len(builds))
    else:
        return

    states = []

    for build in builds:
        # Is this the project we are watching?
        if re.search(main_build + '.+?', build[0]):
            builder, build, status = build[0], build[1], build[5]

            if status == 'success':
                states.append(1)
            else:
                states.append(0)

            message = "'%s' build %s is %s" % (builder, build, status)
            if status == 'success':
                logging.info(message)
            else:
                logging.warn(message)

    last_time = now
    if len(states) == 0:
        return

    """
    This odd bit of logic is a reduction of the set of build results. Only green light
    if all builds are OK.
    """
    sum = 0
    for x in states:
        sum = sum + x
    if sum < len(states):
        current_color = RED
    else:
        current_color = GREEN
    logging.debug('sum: %d count: %d color: %s' % (sum, len(states), current_color))

def ab_main(o):
    """
    Glue it all together. Parse the command line, setup logging, start the
    timers, connect up website.
    """
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

    bbot_url = o.opts['bboturl']
    main_build = o.opts['build']
    port = o.opts['port']
    wsport = o.opts['wsport']
    host = o.opts['hostname']
    interval = int(o.opts['interval'])

    logging.info('Setting up a looping call to the poller, %d seconds' % interval)
    pt = task.LoopingCall(poll_buildbot, bbot_url, main_build)
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
