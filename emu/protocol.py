#!/usr/bin/env python
# -*- coding: utf-8 -*-

from utils import SequenceNumber, symbols

class ProtocolError(Exception):
    "Base exception for protocol errors."

class BadBlockCheckCharacterError(ProtocolError):
    "Raised in parse_message() when BCC is bad"

class MalformedMessageError(ProtocolError):
    "Raised in parse_message() when the message is malformed"

class OutOfRangeError(ProtocolError):
    "Raised for values out of range"


class Protocol(object):

    _seq_number = None
    _default_opts = {}

    def _set_options(self, **options):
        opts = self._default_opts.copy()
        opts.update(options)

        # FIXME: This method needs revision
        self._commandRange = options.get('commandRange', (0x20, 0x7f))
        self._sequenceRange = options.get('sequenceRange', (0x20, 0x7f))

    def __init__(self, **options):
        self._set_options(**options)
        self._seq_number = SequenceNumber(*self._sequenceRange)

    def build_message(self, command, *params):
        """
        Build a message from a command and parameters
        with STX, ETX and BCC marks and next Sequence Number.
        Ready for send as request to the device.
        """
        seq = self._seq_number.next()
        return self.build_message_with_seq(command, seq, *params)

    def build_message_with_seq(self, command, seq, *params):
        """
        Build a message from a command, sequence number and parameters
        see build_message() for more detail. This method is suitable when
        we need to set an explicit sequence number like when we are implementing
        an emulation device.
        """
        if isinstance(seq, int):
            seq = chr(seq)

        if not self._check_sequence_range(seq):
            raise OutOfRangeError("seq %r out of valid range (%x, %x)" % \
                                  (seq, self._sequenceRange[0], self._sequenceRange[1]))

        if not self._check_command_range(seq):
            raise OutOfRangeError("Command %r out of valid range (%x, %x)" % \
                                  (command, self._commandRange[0], self._commandRange[1]))

        params = self.build_params(params)

        msg = symbols.STX + seq + command + params + symbols.ETX
        bcc = self._makeBCC(msg)
        return msg + bcc

    def parse_message(self, message, check_sequence_number=True):
        if not self._checkBCC(message):
            received = message[-4:]
            expected = self._makeBCC(message[:-4])
            raise BadBlockCheckCharacterError("received: %r, expected: %r in message: %r " % \
                    (received, expected, message))

        # Cut off bcc
        message = orig_message = message[:-4]

        head, stx, message = message.partition(symbols.STX)
        if head:
            raise MalformedMessageError("%r isn't the first character in %r" % (stx, orig_message))

        message, etx, tail = message.rpartition(symbols.ETX)
        if tail:
            raise MalformedMessageError("%r isn't the last character in %r" % (etx, orig_message))

        seq_no = message[0]
        if check_sequence_number:
            if seq_no != repr(self._seq_number):
                raise ValueError("Inconsistent sequence number %r, we are waiting for %r" % \
                                 (ord(seq_no), ord(repr(self._seq_number))))
            seq_no = ''

        command = message[1]
        if not self._check_command_range(command):
            raise ValueError("Command %r out of valid range" % command)

        params = self.parse_params(message[2:])

        if seq_no:
            return [ord(seq_no), command] + params
        else:
            return [command] + params

    def build_params(self, params):
        "Build a stream with parameters separated by self.FS (FieldSeparator)"
        if not params:
            return ""
        return symbols.FS + symbols.FS.join(params)

    def parse_params(self, s):
        "Return a list of parameters"
        if not s:
            return []
        orig_s = s
        head, fs, s = s.partition(symbols.FS)
        if head:
            raise MalformedMessageError("%r isn't the first character in parameters substring %r" % \
                                        (fs, orig_s))

        return s.split(symbols.FS)

    def _makeBCC(self, s):
        "Return Block Check Character of message"
        return "%.4X" % sum([ord(c) for c in s])

    def _checkBCC(self, message):
        "Return True if Block Check Character its OK, False otherwise"
        return self._makeBCC(message[:-4]) == message[-4:].upper()

    def _check_command_range(self, command):
        assert len(command) == 1, "Command isn't a character"
        return self._commandRange[0] < ord(command) < self._commandRange[1]

    def _check_sequence_range(self, sequence):
        assert len(sequence) == 1, "Sequence isn't a character"
        return self._sequenceRange[0] < ord(sequence) < self._sequenceRange[1]
