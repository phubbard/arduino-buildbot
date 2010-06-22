
import logging

from twisted.application import service
from twisted.application import internet

from twisted.web import server
from twisted.internet import reactor
from twisted.python import usage

from server import *

logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

application = service.Application('arduino-buildbot')


class ALOptions(usage.Options):
    optParameters = [
        ['port', 'p', 80, 'TCP port to connect to'],
        ['wsport', 'w', 2000, 'TCP port to run webserver on'],
        ['hostname', 'h', 'ooi-arduino.ucsd.edu', 'hostname or IP to connect to'],
        ['build', 'b', 'lcaarch', 'Prefix for build(s) to monitor'],
        ['bboturl', 'u', 'http://ooici.net:8010/xmlrpc', 'Buildbot XML-RPC URL'],
        ['interval', 'i', 30, 'Polling interval, seconds'],
    ]

o = ALOptions()

bbot_url = o.opts['bboturl']
main_build = o.opts['build']
port = o.opts['port']
wsport = o.opts['wsport']
host = o.opts['hostname']
interval = int(o.opts['interval'])

logging.info('Setting up a looping call to the poller, %d seconds' % interval)
pt = internet.TimerService(interval, poll_buildbot, bbot_url, main_build)
pt.setServiceParent(service.IServiceCollection(application))

logging.info('Setting up a looping call for the arduino client')
ct = internet.TimerService(interval, reactor.connectTCP, host, port, ACFactory())
ct.setServiceParent(service.IServiceCollection(application))

logging.info('Setting up webserver on port %d' % wsport)

# HTTP interface
root = indexPage()
site = server.Site(root)
ws = internet.TCPServer(wsport, site)
ws.setServiceParent(service.IServiceCollection(application))


