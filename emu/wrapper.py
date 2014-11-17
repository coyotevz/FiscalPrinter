#!/usr/bin/env python
# -*- coding: utf-8 -*-

from drivers.base import FiscalDriver, FiscalDriverException, FiscalDriverError, \
                         NotImplementedCommand, UnknownCommandError
from protocol import Protocol, ProtocolError
from utils import symbols as s

class TransmissionError(Exception):
    "Low level transmission error"

class TimeoutError(Exception):
    "Timeout reached error" 

class CommunicationWrapper(object):

    def __init__(self, port=None, driver=FiscalDriver,
                 protocol=Protocol, debug=False):
        self.serial_port = port or sys.stderr
        assert issubclass(driver, FiscalDriver), "driver param must be a subclass of FiscalDriver"
        assert issubclass(protocol, Protocol), "protocol param must be a subclass of Protocol"
        self.proto = protocol(commandRange=(0x00, 0xff), sequenceRange=(0x00, 0xff))
        self.driver = driver()
        self.debug = debug

    def process_message(self, message):
        self.driver.clean_fiscal_status()
        try:
            msg = self.proto.parse_message(message, False)
        except ProtocolError as e:
            self.manage_exception(e)

        seq, command = msg[:2]
        params = msg[2:]

        seq = self.filter_seq(seq)
        params = self.filter_params(params)

        self.send_control_char('ACK')

        retval = self.execute_command(command, params)
        retval = self.filter_retval(retval)

        self._last_input = message
        self._last_output = self.proto.build_message_with_seq(command, seq, *retval)

        return self._last_output

    def execute_command(self, command, params):
        retval = None
        try:
            callback = self.driver.get_method(command)
            retval = callback(*params)
            if self.debug:
                print "\x1b[32mDEBUG:\x1b[0m %s%r --> %r" % (callback.__name__, tuple(params), retval)
        except FiscalDriverException as e:
            self.manage_exception(e)

        return retval

    def list_commands(self):
        from types import MethodType
        lst = []
        for k, v in self.driver._symbol_table.iteritems():
            if isinstance(v, MethodType):
                v = v.im_func.func_name
            if hasattr(self.driver, v):
                last.append((v, k))
        return lst

    def manage_exception(self, exception):
        # FiscalDriverErrors that must set a status error in FiscalStatus
        if isinstance(exception, FiscalDriverError):
            error_state = getattr(exception, 'error_state', None)
            if error_state:
                self.driver.fiscal_status.set(error_state)
            print "\x1b[31;1m%s:\x1b[37;0m %s (PS: %s, FS: %s)" % \
                    (exception.__class__.__name__, unicode(exception),\
                     self.driver.printer_status.as_hexstr(),\
                     self.driver.fiscal_status.as_hexstr())
            return

        if isinstance(exception, ProtocolError):
            self.send_control_char('NAK')
            return

        # TODO: log the exception
        raise exception

    def filter_retval(self, retval):
        try:
            retval = self.driver.filter_retval(retval)
        except FiscalDriverException as e:
            self.manage_exception(e)
        return retval

    def filter_seq(self, seq):
        try:
            seq = self.driver.filter_seq(seq)
        except FiscalDriverException as e:
            self.manage_exception(e)
        return seq

    def filter_params(self, params):
        try:
            params = self.driver.filter_params(params)
        except FiscalDriverException as e:
            self.manage_exception(e)
        return params

    def send_control_char(self, s):
        self.serial_port.write(s)
        self.serial_port.flush()

    def write(self, message, waitACK=True):
        self.serial_port.write(message)
        self.serial_port.flush()

        if waitACK:
            r = self.serial_port.read(1)
            if r == s.NAK:
                print "NAK received, resending message."
                self.write(message)
            elif r == s.ACK:
                return
            else:
                raise TransmissionError("Unknown response %r (0x%x)" % (r, ord(r)))

    def read(self):
        data = []

        try:
            r = self.serial_port.read(1)
        except IOError as e:
            print "Closed port by external process (finishing...)"
            raise SystemExit(0)

        if r == s.STX:
            data.append(r)
            while r != s.ETX:
                r = self.serial_port.read(1)
                data.append(r)
            bcc = ""
            for i in range(4):
                bcc += self.serial_port.read(1)
            data.append(bcc)
        elif r == s.ACK:
            self.send_control_char(s.ACK)
            return self.read()
        else:
            raise TransmissionError("not ETX received, instaed %r (0x%x)" % (r, ord(r)))

        return "".join(data)

    def loop(self):

        while True:
            try:
                request_message = self.read()
            except TransmissionError as te:
                print "Bad Request: %s" % te
                self.send_control_char(s.NAK)
                continue

            self.send_control_char(s.ACK)

            response_message = self.process_message(request_message)

            self.write(response_message)
