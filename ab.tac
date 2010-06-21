#!/usr/bin/env python

"""
@file ab.tac
@author Paul Hubbard
@date 6/21/10
@brief Twistd wrapper for buildbot server interface
"""

import os

from twisted.internet.defer import inlineCallbacks
from twisted.application import service

from twisted.application import service, internet
import logging

from server import *

@inlineCallbacks
def make_ab(application):
    logging.info('Starting up')

    abs = ab_main()
    abs.setServiceParent(application)
    
    # code here...

application = service.Application('Arduino buildbot service')
make_ab(application)
