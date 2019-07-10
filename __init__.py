#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import cashier
from . import close


def register():
    Pool.register(
        cashier.Cashier,
        cashier.CreditCardTerminal,
        cashier.CreditCard,
        close.Close,
        close.Document,
        module='cashier', type_='model')
