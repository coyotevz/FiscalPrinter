#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time

from wrapper import CommunicationWrapper
from drivers.base import FiscalDriver
from drivers.hasar import Hasar615

def main(tty_name, debug=False):

    try:
        tty = open(tty_name, "r+", 0)
    except IOError as e:
        print e
        raise SystemExit(0)

    comm = CommunicationWrapper(port=tty, driver=Hasar615, debug=debug)
    try:
        comm.loop()
    except KeyboardInterrupt as k:
        sys.exit(0)
    finally:
        tty.close()

if __name__ == '__main__':
    debug = False
    if "-d" in sys.argv:
        debug = True
        sys.argv.remove("-d")
    main(sys.argv[1], debug)
