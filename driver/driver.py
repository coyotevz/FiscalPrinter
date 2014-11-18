# -*- coding: utf-8 -*-

import random
import time
import serial

_fiscal_status = [
    (1<<0, "Error en memoria fiscal"),
    (1<<1, "Error en comprobación en memoria de trabajo"),
    (1<<2, "Poca batería"),
    (1<<3, "Comando no reconocido"),
    (1<<4, "Campo de datos no válido"),
    (1<<5, "Comando no válido para el estado fiscal"),
    (1<<6, "Desbordamiento de totales"),
    (1<<7, "Memoria fiscal llena"),
    (1<<8, "Memoria fiscal casi llena"),
    (1<<11, "Es necesario hacer un cierre de jornada fiscal o se superó la "\
            "cantidad de tickets en una factura."),
]

_printer_status = [
    (1<<2, "Error y/o falla de la impresora"),
    (1<<3, "Impresora fuera de línea"),
    (1<<6, "Buffer de impresora lleno"),
    (1<<8, "Tapa de impresora abierta"),
]


ACK = chr(0x06)
NAK = chr(0x15)
STATPRN = chr(0xa1)
DC2 = chr(0x12)
DC4 = chr(0x14)
STX = chr(0x02)
ETX = chr(0x03)
FS = chr(0x1c)


class PrinterException(Exception):
    pass

class PrinterStatusError(PrinterException):
    pass

class FiscalStatusError(PrinterException):
    pass

class CommunicationError(PrinterException):
    pass


def _check_status(status, statuses, toraise):
    x = int(status, 16)
    for value, message in statuses:
        if (value & x) == value:
            raise toraise(message)

def _check_printer_status(status):
    _check_status(status, _printer_status, PrinterStatusError)

def _check_fiscal_status(status):
    _check_status(status, _fiscal_status, FiscalStatusError)

def _check_bcc(message, bcc):
    log.debug("message", message, [ord(x) for x in message])
    check_sum = sum([ord(x) for x in message])
    check_sum_h = ("0000" + hex(check_sum)[2:])[-4:].upper()
    log.debug("check sum: ", check_sum, " (hex): ", check_sum_h)
    log.debug("bcc: ", bcc)
    return check_sum_h == bcc.upper()

def _parse_reply(reply, skip_errors):
    r = reply[4:-1] # remove STX <seq_number> <command> <sep> ... ETX
    fields = r.split(FS)
    if not skip_errors:
        printer_status, fiscal_status = fields[:2]
        _check_printer_status(printer_status)
        _check_fiscal_status(fiscal_status)
    return fields



class FiscalDriver(object):
    WAIT_TIME = 10
    RETRIES = 4
    WAIT_CHAR_TIME = 0.1
    NO_REPLY_TRIES = 200

    def __init__(self, device, speed=9600):
        self._serial = serial.Serial(port=device, timeout=None, baudrate=speed)

        # init sequence number
        self._seq_number = random.randint(0x20, 0x7f)
        if self._seq_number % 2:
            self._seq_number -= 1

    def _increment_seq_number(self):
        self._seq_number += 2
        if self._seq_number > 0x7f:
            self._seq_number = 0x20

    def _write(self, string):
        log.debug("_write", ", ".join(["%x" % ord(c) for c in string]))
        self._serial.write(string)

    def _read(self, count):
        ret = self._serial.read(count)
        log.debug("_read", ", ".join(["%x" % ord(c) for c in ret]))
        return ret

    def _send_message(self, message):
        self._send_wait_ack(message)
        timeout = time.time() + self.WAIT_TIME
        retries = 0
        while True:
            if time.time() > timeout:
                raise CommunicationError(u"Expiró el tiempo de espera de "\
                        u"respuesta de la impresora. Revise la conexión")
            c = self._read(1)
            if len(c) == 0:
                continue
            elif c in (DC2, DC4):
                timeout += self.WAIT_TIME
                continue
            elif c == STX:
                reply = c
                noreply_counter = 0
                while c != ETX:
                    c = self._read(1)
                    if not c:
                        noreply_counter += 1
                        time.sleep(self.WAIT_CHAR_TIME)
                        if noreply_counter > self.NO_REPLY_TRIES:
                            raise CommunicationError(u"Falla de comunicación "\
                                u"mientras se recibía respuesta de la impresora")
                    else:
                        noreply_counter = 0
                        reply += c
                bcc = self._read(4)
                if not _check_bcc(reply, bcc):
                    # Send NAK and wait new answer
                    self._write(NAK)
                    timeout = time.time() + self.WAIT_TIME
                    retries += 1
                    if retries > self.RETRIES:
                        raise CommunicationError(u"Falla de comunicación, "\
                                u"demasiados paquetes invalidos (bad bcc).")
                    continue
                elif reply[1] != chr(self._seq_number):
                    # Resend message
                    self._write(ACK)
                    timeout = time.time() + self.WAIT_TIME
                    retries += 1
                    if retries > self.RETRIES:
                        raise CommunicationError(u"Falla de comunicación, "\
                                u"demasiados paquetes invalidos (bad seq_no).")
                    continue
                else:
                    self._write(ACK)
                    break
        return reply

    def _send_wait_ack(self, message, count=0):
        if count > 10:
            raise CommunicationError(u"Demasiados NAK desde la impresora. "\
                    u"Revise la conexión")
        self._write(message)
        timeout = time.time() > self.WAIT_TIME
        while True:
            if time.time() > timeout:
                raise CommunicationError(u"Expiró el tiempo de espera de "\
                        u"respuesta de la impresora. Revise la conexión")
            c = self._read(1)
            if len(c) == 0:
                continue
            elif c == ACK:
                return True
            elif c == NAK:
                return self._send_wait_ack(message, count+1)

    def __del__(self):
        if hasattr(self, "_serial"):
            try:
                self.close()
            except:
                pass

    def close(self):
        try:
            self._serial.close()
        except:
            pass
        del self._serial

    def send_command(self, command, fields, skip_errors=False):
        msg = STX + chr(self._seq_number) + chr(command)
        if fields:
            msg += FS + FS.join(fields)
        msg += ETX
        check_sum = sum([ord(x) for x in msg])
        msg += ("0000" + hex(check_sum)[2:])[-4:].upper()
        reply = self._send_message(msg)
        self._increment_seq_number()
        return _parse_reply(reply, skip_errors)
