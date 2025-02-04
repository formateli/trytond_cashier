#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


class Receipt(metaclass=PoolMeta):
    __name__ = 'cash_bank.receipt'
    cashier_close = fields.Many2One(
        'cashier.close', 'Cashier Close')

    @classmethod
    def copy(cls, receipts, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('cashier_close', None)
        return super().copy(receipts, default=default)
