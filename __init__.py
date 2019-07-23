#This file is part of Tryton cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import configuration
from . import cashier
from . import close
from . import sale


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationSequences,
        configuration.ConfigurationParties,
        configuration.ConfigurationAccounts,
        cashier.Cashier,
        cashier.CreditCardTerminal,
        cashier.CreditCard,
        close.Close,
        close.Document,
        close.CreditCardTerminalMove,
        close.CustomerReceivable,
        close.CustomerPayable,
        close.CloseLog,
        sale.Sale,
        module='cashier', type_='model')
