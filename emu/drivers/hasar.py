#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
from datetime import datetime
from collections import namedtuple
from decimal import Decimal

from drivers.base import FiscalDriver, FiscalStatus, PrinterStatus, \
                         FiscalDriverError, NotValidDataError, \
                         NotValidCommandError, NotImplementedCommand
from utils import command
from config import config

class NotValidDateData(FiscalDriverError):
    error_state = "bad date"

class Hasar615FiscalStatus(FiscalStatus):

    __statuses__ = {
        "certified terminal":   9,
        "fiscalized terminal":  10,
        "bad date":             11,
        "open fiscal document": 12,
        "open document":        13,
        "unused":               14,
        "quick status check":   15,
    }

CustomerData = namedtuple("CustomerData", "nombre cuit responsabilidad tipo_doc")
FiscalDocument = namedtuple("FiscalDocument", "type number items")
FiscalItem = namedtuple("FiscalItem", "desc cantidad monto iva signo k total")
DiscountItem = namedtuple("DiscountItem", "desc monto signo total")

_customer_type = {
    'I': 'RESPONSABLE INSCRIPTO',
    'N': 'RESPONSABLE NO INSCRIPTO',
    'E': 'EXENTO',
    'A': 'NO RESPONSABLE',
    'C': 'CONSUMIDOR FINAL',
    'M': 'RESPONSABLE MONOTRIBUTO',
    'B': 'RESPONSABLE NO INSCRIPTO, BIENES DE USO',
}

class Hasar615PrinterStatus(PrinterStatus):

    __statuses__ = {
            "printer error": 2,
            "printer offline": 3,
    }

class Hasar615(FiscalDriver):

    brand_name = 'Hasar'
    model_name = 'SMH/P 615F'

    def __init__(self):
        super(Hasar615, self).__init__(
                fiscal_status_cls=Hasar615FiscalStatus,
                printer_status_cls=Hasar615PrinterStatus
        )
        self._init_memory()
        self._clean_work_memory()
        self._last_number = {
            "A": self.EPROM['last_counter_A'],
            "B": self.EPROM['last_counter_B'],
        }

        self.fiscal_status.set("certified terminal")
        self.fiscal_status.set("fiscalized terminal")
        #self.fiscal_status.set("fiscal memory full")
        #self.fiscal_status.set("low battery")

    def StatusRequest(self, *params):
        ret = self.printer_status.as_hexstr(), self.fiscal_status.as_hexstr()
        return ret

    @command('\x58')
    def SetDateTime(self, *params):
        try:
            new_time = datetime.strptime("|".join(params), "%y%m%d|%H%M%S")
        except ValueError as e:
            raise NotValidDateData("Error en el ingreso de fecha: '%s'" % "|".join(params))
        self.fiscal_status.unset("bad date")
        print "[INFO] * Setting time to %s" % (new_time.isoformat(),)
        return self.StatusRequest()

    @command('\x59')
    def GetDateTime(self, *params):
        now = datetime.now()
        fecha = now.date().strftime('%y%m%d')
        hora = now.time().strftime('%H%M%S')
        return self.StatusRequest() + (fecha, hora)

    @command('\x62')
    def SetCustomerData(self, *params):
        if self._current_document is not None:
            raise NotValidCommandError(u"existe un documento abierto")

        self._customer_data = CustomerData(*params)
        if self._customer_data.tipo_doc == 'C':
            if not self._validate_cuit(self._customer_data.cuit):
                bad_cuit = self._customer_data.cuit
                self._customer_data = None
                raise NotValidDataError(u"CUIT inválido (%s)" % bad_cuit)

        # TODO: verificar coherencia 'Responsabilidad frente al IVA' y 'CUIT o documento'

        return self.StatusRequest()

    @command('\x5d') # ']'
    def SetHeaderTrailer(self, *params):
        lineno, text = params
        if text == '\x7f':
            self.HEADERTRAILER[int(lineno)] = ""
        else:
            self.HEADERTRAILER[int(lineno)] = text[:40]
        return self.StatusRequest()

    @command('\x40') # '@'
    def OpenFiscalReceipt(self, *params):
        if self._current_document is not None:
            raise NotValidCommandError(u"ya existe un documento abierto")

        _customer_doc_type = {'0': 'L.E.  ',
                              '1': 'L.C.  ',
                              '2': 'D.N.I.',
                              '3': 'Pasap.',
                              '4': 'C.I.  '}

        # TODO: Obtener numero de comprobante de algun acumulador
        self._current_document = FiscalDocument(params[0], self._last_number[params[0]]+1, [])

        if self._current_document.type == 'A':
            if self._customer_data is None:
                raise NotValidCommandError(u"no se habian ingresado los datos del cliente")
            elif self._customer_data.responsabilidad not in ('I', 'N'):
                raise NotValidCommandError(u"el cliente no cumple los requisitos para este comprobante")

        # Imprimimos el encabezado
        #print "\x1b[31m" + " inicio ".center(40, "-") + "\x1b[0m"
        print "\x1b[31m" + "8<------8<".center(40, "-") + "\x1b[0m"
        for i in [1, 2]:
            self._print_out_line(self.FANTASY[i])
        self._print_out_line(self.EPROM['razon_social'])
        self._print_out_line("C.U.I.T. Nro : %s" % self.EPROM['cuit'])
        self._print_out_line(" INGRESOS BRUTOS : %s" % self.EPROM['ib'])
        for i in [1, 2, 3, 4]:
            self._print_out_line(self.HEADERTRAILER[i])
        self._print_out_line("INICIO DE ACTIVIDADES : %s" % self.EPROM['inicio'])
        self._print_out_line("IVA RESPONSABLE INSCRIPTO")
        for i in [5, 6, 7]:
            self._print_out_line(self.HEADERTRAILER[i])
        self._print_separator()
        self._print_out_line('TIQUE FACTURA   \x1b[;1m" %s "\x1b[0m' % self._current_document.type +\
                             '  Nro.%04d' % int(self.EPROM['pv']) +\
                             '-%08d' % int(self._current_document.number))
        self._print_date_time()
        self._print_separator()

        if self._customer_data is not None:
            self._print_out_line(self._customer_data.nombre)
            cuit = self._customer_data.cuit
            if self._customer_data.tipo_doc == 'C':
                self._print_out_line("CUIT  : %s" % "-".join([cuit[:2], cuit[2:10], cuit[10]]))
            elif self._customer_data.tipo_doc in _customer_doc_type:
                self._print_out_line("%s: %s" % (_customer_doc_type[self._customer_data.tipo_doc], cuit))
            ct = _customer_type.get(self._customer_data.responsabilidad, '<NO VALUE>')
        else:
            ct = _customer_type['C']
        self._print_out_line("A %s" % ct)
        for i in [8, 9, 10]:
            self._print_out_line(self.HEADERTRAILER[i])
        self._print_separator()
        self._print_out_line("CANTIDAD/PRECIO UNIT (% IVA)")
        self._print_out_line("DESCRIPCION          [%B.I.]     IMPORTE")
        self._print_separator()

        self._customer_data = None
        self._can_add_item = True

        return self.StatusRequest()

    @command('\x41') # 'A'
    def PrintFiscalText(self, *params):
        text, display = params
        if self._current_document is None:
            raise NotValidCommandError(u"no hay un documento abierto")

        if len(self._fiscal_text) >= 3 or \
           (len(self._fiscal_text) >= 2 and self._current_document.type == 'T'):
            raise NotValidCommandError(u"se excede la cantidad de 'PrintFiscalText' permitidos")

        self._fiscal_text.append("%s" % text[:28])

        return self.StatusRequest()

    @command('\x42') # 'B'
    def PrintLineItem(self, *params):

        if self._current_document is None:
            raise NotValidCommandError(u"no hay documento abierto")
        if not self._can_add_item:
            raise NotValidCommandError(u"no se pueden agregar mas items")
        try:
            desc, cantidad, monto, iva, signo, k, display, total = params
        except ValueError as e:
            raise NotValidDataError(u"cantidad de parametros incorrectos (%s)" % len(params))

        if iva == '**.**':
            return self.GeneralDiscount(desc, monto, signo, display, 'T')

        item = FiscalItem(desc, Decimal(cantidad), Decimal(monto), Decimal(iva), signo, Decimal(k), total)

        self._current_document.items.append(item)

        if item.total == 'T' and self._current_document.type == "A":
            monto = item.monto / Decimal('1.21')
        elif item.total != 'T' and self._current_document.type != "A":
            monto = item.monto * Decimal('1.21')
        else:
            monto = item.monto

        s = "%.3f / %.2f" % (item.cantidad, monto)
        i = "(%05.2f)" % item.iva
        self._print_out_line(s.ljust(22) + i.ljust(18))

        for ft in self._fiscal_text:
            self._print_out_line(ft)
        self._fiscal_text = []

        bi = " "*7
        if float(item.k) != 0:
            # TODO: imprimir (%B.I.) segun corresponda
            pass

        desc = "%s" % item.desc
        monto_str = "%.2f" % (monto*item.cantidad)
        self._print_out_line(desc.ljust(22) + bi.rjust(8) + monto_str.rjust(10))
        return self.StatusRequest()

    @command('\x54')
    def GeneralDiscount(self, *params):
        if self._current_document is None:
            raise NotValidCommandError(u"no hay documento abierto")
        if len(self._current_document.items) < 1:
            raise NotValidCommandError(u"no hubo una venta previa")
        try:
            desc, monto, signo, display, total = params
        except ValueError:
            raise NotValidDataError(u"cantidad de parametros incorrectos (%s)" % len(params))

        item = DiscountItem(desc, Decimal(monto), signo, total)
        self._current_document.items.append(item)
        monto = "%-.2f" % (item.monto if item.signo == "M" else -item.monto)
        self._print_out_line(item.desc.ljust(30) + monto.rjust(10))
        self._can_add_item = False

        return self.StatusRequest()

    @command('\x43') # 'C'
    def Subtotal(self, *params):
        if self._current_document is None:
            raise NotValidCommandError(u"no hay documento abierto")
        try:
            imprimir, _, display = params
        except ValueError as e:
            raise NotValidDataError(u"cantidad de parametros incorrectos (%s)" % len(params))

        total, items, iva = self._calcular_totales()

        return self.StatusRequest() + (str(items), str(total), str(0), str(0), str(0), str(0))

    @command('\x44') # 'D'
    def TotalTender(self, *params):
        if self._current_document is None:
            raise NotValidCommandError(u"no hay documento abierto")

        try:
            text, monto, op, display = params[:4]
        except ValueError as e:
            raise NotValidDataError(u"cantidad de parametros incorrectos (%s)" % len(params))

        if op == 'T':
            self._print_totals()

            monto = Decimal(monto)
            self._print_out_line("RECIBI/MOS")
            self._print_out_line(("%s" % text).ljust(30) + ("%.2f" % monto).rjust(10))
            return self.StatusRequest() + (str(0.0),)
        else:
            raise NotImplementedCommand(u"esta opcion todavia no se implementa")

    @command('\x45') # 'E'
    def CloseFiscalReceipt(self, *params):
        if self._current_document is None:
            raise NotValidCommandError(u"no hay documento abierto")

        self._print_totals()

        for i in [11, 12, 13, 14]:
            self._print_out_line(self.HEADERTRAILER[i])
        self._print_out_line("\x1b[30;1m" + "  CF" + "\x1b[0m"+"      V: 01.02")
        self._print_out_line("\x1b[30;1m" + " DGI" + "\x1b[0m"+"      Reg.:NNG0003137")

        #print "\x1b[31m" + " fin ".center(40, "-") + "\x1b[0m"
        print "\x1b[31m" + ">8------>8".center(40, "-") + "\x1b[0m"

        self._last_number[self._current_document.type] = n = self._current_document.number
        # Reset some variables
        self._clean_work_memory()

        return self.StatusRequest() + (str(n),)

    @command('\x4a') # 'J'
    def CloseNonFiscalReceipt(self, *params):
        return self.StatusRequest()

    @command('\x39') # '9'
    def DailyClose(self, *params):
        if self._current_document is not None:
            raise NotValidCommandError(u"existe un documento abierto")
        try:
            close_type, = params
        except ValueError as e:
            raise NotValidDataError(u"cantidad de parametros incorrectos (%s)" % len(params))

        print "DailyClose('%s') requested" % close_type

        return self.StatusRequest()

    ## Internal Methods

    def _print_totals(self):
        if not self._total_printed:
            self._total_printed = True
            total, items, iva = self._calcular_totales()

            if self._current_document.type == "A":
                neto = "%.2f" % (total/Decimal('1.21'),)
                iva_str = "%.2f" % iva
                print
                self._print_out_line("NETO SIN IVA".ljust(30) + neto.rjust(10))
                self._print_out_line("IVA 21.00 %".ljust(30) + iva_str.rjust(10))
            print
            self._print_out_line("\xf4TOTAL" + (" %.2f" % total).rjust(15))

    def _calcular_totales(self):
        assert self._current_document is not None, u"BUG! no hay documento abierto"
        total = Decimal(0)
        iva = Decimal(0)
        items_count = 0

        for item in self._current_document.items:
            if item.total == 'T':
                iiva = (item.monto/Decimal('1.21')) * Decimal('0.21')
                monto = item.monto
            else:
                iiva = (item.monto*Decimal('0.21'))
                monto = item.monto * Decimal('1.21')

            if isinstance(item, FiscalItem):
                if item.signo == 'M':
                    total += item.cantidad * monto
                    items_count += 1
                    iva += iiva * item.cantidad
                elif item.signo == 'm':
                    total -= item.cantidad * monto
                    items_count -= 1
                    iva -= iiva * item.cantidad
            elif isinstance(item, DiscountItem):
                if item.signo == 'M':
                    total += item.monto
                    iva += iiva
                elif item.signo == 'm':
                    total -= item.monto
                    iva -= iiva

        return total, items_count, iva

    def _print_out_line(self, message, align='left'):
        time.sleep(0.02)
        if message:
            if message[0] == '\xf4':
                message = '\x1b[;1m%s\x1b[0m' % (" "+" ".join(list(message[1:]))[:40])
            if align == 'left':
                print message.ljust(40)
            elif align == 'right':
                print message.rjust(40)
            else: # center
                print message.center(40)
        sys.stdout.flush()

    def _print_separator(self):
        print "-"*40

    def _print_date_time(self):
        now = datetime.now()
        self._print_out_line("Fecha : %s" % now.date().strftime('%d-%m-%y'), align="right")
        self._print_out_line("Hora  : %s" % now.time().strftime('%H:%M:%S'), align="right")

    def _init_memory(self):
        self.HEADERTRAILER = config['HEADERTRAILER']
        self.FANTASY = config['FANTASY']
        self.EPROM = config['EPROM']

    def _clean_work_memory(self):
        self._customer_data = None
        self._fiscal_text = []
        self._current_document = None
        self._can_add_item = False
        self._total_printed = False

    def _validate_cuit(self, cuit):
        """Validar CUIT:
        Devuelve `True` si el CUIT tiene la longitud, el formato correcto y su
        dígito verificador esta OK.
        from: http://python.org.ar/pyar/Recetario/ValidarCuit
        """
        # validaciones mínimas
        if len(cuit) != 11:
            return False

        base = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

        # calculo el dígito verificador
        aux = 0
        for i in xrange(10):
            aux += int(cuit[i]) * base[i]

        aux = 11 - (aux-(int(aux/11)*11))

        if aux == 11:
            aux = 0
        if aux == 10:
            aux = 9

        return aux == int(cuit[10])
