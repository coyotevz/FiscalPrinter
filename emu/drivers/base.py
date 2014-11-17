#!/usr/bin/env python
# -*- coding: utf-8 -*-

from utils import Status

class FiscalDriverException(Exception):
    "Base exception for FiscalDriver object"

class FiscalDriverError(FiscalDriverException):
    "Base error for FiscalDriver object"

class UnknownCommandError(FiscalDriverError):
    """
    Comando desconocido

    El comando recibido no fue reconocido.
    """
    error_state = "unknown command"

class NotImplementedCommand(FiscalDriverError):
    """
    Comando no implementado (desarrollo)

    Especial para el desarrollo del emulador, el comando aparece en la lista
    de comando pero no existe el método en el driver correspondiente.
    """
    error_state = "unknown command"

class NotValidDataError(FiscalDriverError):
    """
    Datos no válidos en un campo

    Uno de los campos del comando recibido tiene datos no válidos
    (por ejemplo, datos no numéricos en un campo numérico).
    """
    error_state = "not valid data"

class NotValidCommandError(FiscalDriverError):
    """
    Comando no válido para el estado fiscal actual

    Se ha recibido un comando que no es válido en el estado actual del
    controlador (por ejemplo, abrir un recibo no-fiscal cuando se encuentra
    abierto un recibo fiscal).
    """
    error_state = "not valid command"

class FiscalStatus(Status):
    __statuses__ = {
        "error fiscal memory":       0,
        "error work memory":         1,
        "low battery":               2,
        "unknown command":           3,
        "not valid data":            4,
        "not valid command":         5,
        "overflow of total":         6,
        "fiscal memory full":        7,
        "fiscal memory almost full": 8,
    }
    _quick_status = range(0, 8)

class PrinterStatus(Status):
    __statuses__ = {}

class AuxStatus(Status):
    __statuses__ = {}

class FiscalDriver(object):

    brand_name = None
    model_name = None
    model_variant = None

    _symbol_table = {
        '\x2a': "StatusRequest",
    }

    charset = 'ascii'

    def __init__(self, fiscal_status_cls=FiscalStatus,
            printer_status_cls=PrinterStatus):
        self.fiscal_status = fiscal_status_cls()
        self.printer_status = printer_status_cls()
        self._register_methods()

    def _register_methods(self):
        for key in dir(self):
            method = getattr(self, key)
            if callable(method):
                if hasattr(method, 'symbol'):
                    self._symbol_table[method.symbol] = method

    def get_method(self, symbol):
        method_str = None
        method = self._symbol_table.get(symbol)
        if isinstance(method, basestring):
            method_str = method
            method = getattr(self, method, None)
        if not method and method_str is not None:
            raise NotImplementedCommand("%r (0x%.2x) is in commands table as '%s' but no implemented in %s" % \
                                        (symbol, ord(symbol), method_str, type(self).__name__))
        elif not method or not callable(method):
            raise UnknownCommandError("%r (0x%.2x) not registered in fiscal driver commands table" %\
                                      (symbol, ord(symbol)))
        return method

    def filter_retval(self, retval):
        if retval is None:
            retval = []
        elif not isinstance(retval, (tuple, list)):
            retval = [retval]
        return retval

    def filter_seq(self, seq):
        return seq

    def filter_params(self, params):
        return params

    def clean_fiscal_status(self):
        self.fiscal_status.unset("unknown command")
        self.fiscal_status.unset("not valid data")
        self.fiscal_status.unset("not valid command")
        self.fiscal_status.unset("overflow of total")


class PrinterDriver(object):
    pass
