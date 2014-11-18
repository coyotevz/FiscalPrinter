# -*- coding: utf-8 -*-

from collections import namedtuple

from driver import PrinterException

class Printer(object):
    pass

_text_sizes = {
    "615": {
        'NON_FISCAL_TEXT': 40,
        'CUSTOMER_NAME': 30,
        'CUSTOMER_ADDRESS': 40,
        'PAYMENT_DESCRIPTION': 30,
        'FISCAL_TEXT': 20,
        'LINE_ITEM': 20,
        'LAST_ITEM_DISCOUNT': 20,
        'GENERAL_DISCOUNT': 20,
        'EMBARK_ITEM': 108,
        'RECEIPT_TEXT': 106,
    },
    "320": {
        'NON_FISCAL_TEXT': 120,
        'CUSTOMER_NAME': 50,
        'CUSTOMER_ADDRESS': 50,
        'PAYMENT_DESCRIPTION': 50,
        'FISCAL_TEXT': 50,
        'LINE_ITEM': 50,
        'LAST_ITEM_DISCOUNT': 50,
        'GENERAL_DISCOUNT': 50,
        'EMBARK_ITEM': 108,
        'RECEIPT_TEXT': 106,
    }
}

# type document
DOC_TICKET             = u'TICKET'
DOC_CREDIT_TICKET      = u'CREDIT_TICKET'
DOC_BILL_TICKET        = u'BILL_TICKET'
DOC_CREDIT_BILL_TICKET = u'CREDIT_BILL_TICKET'
DOC_DEBIT_BILL_TICKET  = u'DEBIT_BILL_TICKET'
DOC_DNFH               = u'DNFH' # Documento No Fiscal Homologado
DOC_NON_FISCAL         = u'NON_FISCAL'

# printer commands
CMD_STATUS_REQUEST           = 0x2a
CMD_DAILY_CLOSE              = 0x39
CMD_OPEN_FISCAL_RECEIPT      = 0x40
CMD_PRINT_TEXT_IN_FISCAL     = 0x41
CMD_PRINT_LINE_ITEM          = 0x42
CMD_PRINT_SUBTOTAL           = 0x43
CMD_ADD_PAYMENT              = 0x44
CMD_CLOSE_FISCAL_RECEIPT     = 0x45
CMD_OPEN_NON_FISCAL_RECEIPT  = 0x48
CMD_PRINT_NON_FISCAL_TEXT    = 0x49
CMD_CLOSE_NON_FISCAL_RECEIPT = 0x4a
CMD_GENERAL_DISCOUNT         = 0x54
CMD_LAST_ITEM_DISCOUNT       = 0x55
CMD_SET_HEADER_TRAILER       = 0x5d
CMD_SET_CUSTOMER_DATA        = 0x62
CMD_OPEN_DRAWER              = 0x7b
CMD_OPEN_DNFH                = 0x80
CMD_OPEN_CREDIT_NOTE         = 0x80
CMD_CLOSE_CREDIT_NOTE        = 0x81
CMD_CLOSE_DNFH               = 0x81
CMD_PRINT_EMBARK_ITEM        = 0x82
CMD_PRINT_ACCOUNT_ITEM       = 0x83
CMD_PRINT_QUOTATION_ITEM     = 0x84
CMD_PRINT_DNFH_INFO          = 0x85
CMD_CREDIT_NOTE_REFERENCE    = 0x93
CMD_PRINT_RECEIPT_TEXT       = 0x97
CMD_CANCEL_ANY_DOCUMENT      = 0x98
CMD_REPRINT                  = 0x99

# internal commands
CMD_CLOSE = 'CMD_CLOSE_DOCUMENT'

# iva types
IVA_RESPONSABLE_INSCRIPTO    = 'I'
IVA_RESPONSABLE_NO_INSCRIPTO = 'N'
IVA_EXCENTO                  = 'E'
IVA_NO_RESPONSABLE           = 'A'
IVA_CONSUMIDOR_FINAL         = 'C'
IVA_RESPONSABLE_MONOTRIBUTO  = 'M'

_iva_types = (
    IVA_RESPONSABLE_INSCRIPTO, IVA_RESPONSABLE_NO_INSCRIPTO, IVA_EXCENTO,
    IVA_NO_RESPONSABLE, IVA_CONSUMIDOR_FINAL, IVA_RESPONSABLE_MONOTRIBUTO
)


PrinterItem = namedtuple("PrinterItem",
        "description quantity price iva discount discount_desc negative")
CustomerData = namedtuple("CustomerData",
        "name address id_number id_type iva_type")


class HasarPrinter(Printer):

    def __init__(self, driver):
        self.driver = driver
        self._current = None
        self._customer = None
        self._cmd = []
        self._items = []
        self._payments = []

    def open_bill(self, bill_type):
        assert bill_type in ("A", "B")
        self._current = DOC_BILL_TICKET
        self.command(CMD_OPEN_FISCAL_RECEIPT, [bill_type, "T"])

    def open_ticket(self, ticket_type="B"):
        self._current = DOC_TICKET
        self.command(CMD_OPEN_FISCAL_RECEIPT, [ticket_type, "T"])

    def open_debit_note(self, debit_type):
        assert debit_type in ("A", "B")
        debit_type = {"A": "D", "B": "E"}[debit_type]
        self._current = DOC_DEBIT_BILL_TICKET
        self.command(CMD_OPEN_FISCAL_RECEIPT, [debit_type, "T"])

    def open_credit_note(self, credit_type):
        assert credit_type in ("A", "B")
        credit_type = {"A": "R", "B": "S"}[credit_type]
        self._current = DOC_CREDIT_BILL_TICKET
        self.command(CMD_CREDIT_NOTE_REFERENCE, ["1", "NC"])
        self.command(CMD_OPEN_CREDIT_NOTE, [credit_type, "T"])

    def open_receipt(self):
        self._current = DOC_DNFH
        self.command(CMD_OPEN_DNFH, ["r", "T"])

    def close_document(self):
        assert self._current is not None
        self.command(CMD_CLOSE, [])

    def daily_close(self):
        assert self._current is None
        return self.execute(CMD_DAILY_CLOSE, ["Z"])

    def partial_close(self):
        assert self._current is None
        return self.execute(CMD_DAILY_CLOSE, ["X"])

    def set_customer_data(self, data):
        assert isinstance(data, CustomerData)
        self._customer = data

    def add_item(self, item=None, **kwargs):
        if not isinstance(item, PrinterItem):
            item = PrinterItem(**kwargs)
        self._items.append(item)

    def add_items(self, items):
        for item in items:
            self.add_item(item)

    def execute(self, cmd, args=(), skip_errors=False):
        cmd_str = "SEND|0x%x|%s|%s" %\
                (cmd, "T" if skip_errors else "F", str(args))
        log.debug("execute: %s" % cmd_str)
        try:
            reply = self.driver.send_command(cmd, args)
            log.debug("reply: %s" % reply)
            return reply
        except PrinterException as e:
            log.debug("ERROR: %s" % e.args[0])
            raise PrinterException("Error de la impresora fiscal: %s.\n"
                "Commando enviado: %s" % (e.args[0], cmd_str))

    def command(self, cmd, args):
        self._cmd.append((cmd, args))

    def finish(self):
        """Print out document processing all commands."""

    def close(self):
        self.driver.close()
        self.driver = None

    def __del__(self):
        try:
            self.close()
        except:
            pass
