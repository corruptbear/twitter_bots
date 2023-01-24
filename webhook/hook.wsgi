#!/usr/bin/env python3

import logging
import sys
import os
import glob

pwd = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(filename=os.path.join(pwd,'debug.log'),level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("---------------------------")
logger.info(sys.version)
logger.info(sys.executable)


file_dir = os.path.dirname(__file__)
if file_dir not in sys.path:
    sys.path.append(file_dir)

logger.info(sys.path)

from hook_site import app as application

logger.info('app loaded')
application.secret_key = 'hook'
