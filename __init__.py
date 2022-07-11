#This file is part of Tryton cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import cashier
from . import close
from . import sale
from . import receipt
from . import transfer


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationSequences,
#        configuration.ConfigurationParties,
        configuration.ConfigurationAccounts,
        cashier.Cashier,
        cashier.MoneyTerminal,
        cashier.TerminalMoneyType,
        cashier.TerminalMoneyTypeDiscount,
        cashier.TerminalMoneyTypeDiscountCharge,
        cashier.TerminalMoneyTypeAmount,
        cashier.TerminalMoneyTypeAmountDiscount,
        cashier.TerminalMoneyTypeAmountDiscountCharge,
        cashier.CashierDiscount,
        cashier.MoneyTypeType,
        close.Close,
        close.MoneyTerminalMove,
        close.MoneyTerminalMoveType,
        close.MoneyTerminalMoveAmount,
        close.CustomerReceivable,
        close.CustomerPayable,
        close.ColletedInAdvance,
        close.ColletedInAdvanceApply,
        close.CloseLog,
        sale.Sale,
        receipt.Receipt,
        transfer.Transfer,
        module='cashier', type_='model')
