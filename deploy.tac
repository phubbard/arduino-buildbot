
import logging

from twisted.application import service
from twisted.application import internet

from twisted.web import server
from twisted.internet import reactor, threads
from twisted.python import usage

from server import *
from pachube import update_pachube

logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

application = service.Application('arduino-buildbot')

# Use defaults from the ALOptions
o = ALOptions()
bbot_url = o.opts['bboturl']
main_build = o.opts['build']
port = o.opts['port']
wsport = o.opts['wsport']
host = o.opts['hostname']
interval = int(o.opts['interval'])

logging.info('Setting up a looping call to the poller, %d seconds' % interval)
pt = internet.TimerService(interval, poll_bb_json, bbot_url, main_build)
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
