#!/usr/bin/env python
# -*- coding: utf-8 -*-

from math import ceil, log
from itertools import izip_longest
from random import randint

def groupier(n, iterable, fillvalue=None):
    """groupier(3, 'ABCDEFG', 'x') --> ABC DEF Gxx

    from itertools recipes: http://docs.python.org/dev/library/itertools.html#recipes
    """
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)

def message_hex(s):
    return " ".join(["%02X" % ord(c) for c in s])

def command(symbol):
    def wrapper(function):
        function.symbol = symbol
        return function
    return wrapper


class BitField(object):

    def __init__(self, size=0, **kwargs): # value=None, bitstr=None, hexstr=None, chars=None
        self.fixed_size = bool(int(size) > 0)
        self.size = int(size)
        self._fields = 0
        self.set_value(**kwargs)

    def set_value(self, **kwargs):
        """
        Keyword Arguments: (only 1 at time)
            value: int or list|tuple of booleans or known string ('0x00', '0b00', '1234')
            bitstr: a string of bits ('001010')
            hexstr: a string of hexs ('ba2ef1')
            chars: a string with characters ('\x12b')
        """
        if len(kwargs) > 1:
            raise TypeError("set_value() expected at most 1 named argument, got %d" % len(kwargs))
        elif len(kwargs) == 0:
            self._set_from_value(0)
            return
        _type = kwargs.keys()[0]
        if not _type in ("value", "bitstr", "hexstr", "chars"):
            raise TypeError("unknown named argument '%s'" % _type)

        _set_from = getattr(self, '_set_from_%s' % _type)
        _set_from(kwargs.get(_type))

    def set_bit(self, index, value):
        value = bool(value)
        index = int(index)
        self[index] = value

    def bit_on(self, index):
        self.set_bit(index, True)

    def bit_off(self, index):
        self.set_bit(index, False)

    def as_bitstr(self, fill=None):
        b = bin(self)[2:]
        return b.zfill(fill or self.size)

    def as_hexstr(self, fill=None):
        h = hex(self)[2:]
        nibbles = self.size / 4 + int(bool(self.size % 4))
        return h.zfill(fill or nibbles)

    def as_chars(self, fill=None):
        bytes = self.size / 8 + int(bool(self.size % 8))
        s = ("%x" % int(self)).zfill(bytes*2)
        return s.decode("hex")

    def _set_from_value(self, value):
        if isinstance(value, (list, tuple)):
            self._set_from_bitstr("".join(["%d" % int(bool(b)) for b in value]))
            return
        elif isinstance(value, basestring):
            if value.startswith('0x'):
                self._set_from_hexstr(value)
            elif value.startswith('0b'):
                self._set_from_bitstr(value)
                return
        self._set_from_int(int(value))

    def _set_from_bitstr(self, bitstr):
        self._set_from_int(int(bitstr, 2))

    def _set_from_hexstr(self, hexstr):
        self._set_from_int(int(hexstr, 16))

    def _set_from_int(self, value):
        if self.fixed_size:
            if value > (2**self.size) - 1:
                raise ValueError("%d exced maximun value %d" % (value, 2**self.size-1))
        new_size = int(ceil(log(value+1, 2)))
        self.size = max(self.size, new_size)
        self._fields = value

    def _set_from_chars(self, value):
        pass

    def __repr__(self):
        return self.as_bitstr()

    def __int__(self):
        return self._fields

    def __hex__(self):
        return hex(int(self))

    def __str__(self):
        return self.as_chars()

    def __len__(self):
        return self.size

    def __iter__(self):
        return iter(int(i) for i in repr(self))

    def __index__(self):
        return int(self)

    def __getitem__(self, i):
        if isinstance(i, int):
            if self.fixed_size:
                if i > self.size-1:
                    raise IndexError("BitField index out of range")
                if i < 0: i = self.size - i
            return bool(self._fields & 1 << i)
        elif isinstance(i, slice):
            start, stop, step = i.indices(self.size)
            return [self[i] for i in xrange(start, stop, step)]
        raise TypeError("BitField indices must be integers, not %s" % type(i).__name__)

    def __setitem__(self, i, value):
        if isinstance(i, int):
            value = bool(value)
            if self.fixed_size:
                if i > self.size-1:
                    raise IndexError("BitField index out of range")
                if i < 0: i = self.size-1
            if value:
                self._fields = self._fields | 1 << i
            else:
                if self[i]:
                    self._fields = self._fields ^ 1 << i
            return
        elif isinstance(i, slice):
            raise TypeError("You must assign values one by one")
        raise TypeError("BitFields indices must be integers, not %s" % type(i).__name__)

class StatusMetaclass(type):

    def __init__(cls, name, bases, ns):
        type.__init__(cls, name, bases, ns)
        statuses = getattr(bases[0], '__statuses__', {}).copy()
        new_statuses = getattr(cls, '__statuses__', {})
        statuses.update(new_statuses)
        setattr(cls, '__statuses__', statuses)

class Status(BitField):
    __metaclass__ = StatusMetaclass

    __statuses__ = {}
    _quick_status = []

    def __init__(self):
        super(Status, self).__init__(16)

    def _status_index(self, status):
        if status not in self.__statuses__:
            raise ValueError("unknown status '%s', __statuses__ = %r" % (status, self.__statuses__))
        return self.__statuses__[status]

    def _build_quick_status(self):
        value = any([self[i] for i in self._quick_status])
        index = self.__statuses__.get("quick status check", None)
        if index is not None:
            self.set_bit(index, value)

    def set(self, status):
        index = self._status_index(status)
        self.bit_on(index)
        self._build_quick_status()

    def unset(self, status):
        index = self._status_index(status)
        self.bit_off(index)
        self._build_quick_status()

    def is_set(self, status):
        index = self._status_index(status)
        return self[index]


class SequenceNumber(object):

    def __init__(self, start, end):
        self._start = start
        self._end = end
        self.reset()

    def reset(self):
        self._current = randint(self._start, self._end)

    def next(self):
        if self._current >= self._end:
            self._current = self._start
        else:
            self._current += 1
        return chr(self._current)

    def __iter__(self):
        return self

    def __repr__(self):
        return chr(self._current)


class _symbols(object):
    STX = '\x02'
    ETX = '\x03'
    ACK = '\x06'
    NAK = '\x07'
    DC1 = '\x11'
    DC2 = '\x12'
    DC3 = '\x13'
    DC4 = '\x14'
    ESC = '\x1b'
    FS  = '\x1c'

symbols = _symbols()
