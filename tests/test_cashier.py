# This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.pool import Pool
#from trytond.transaction import Transaction
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
#from trytond.modules.company.tests import create_company, set_company
#from decimal import Decimal


class CashierTestCase(ModuleTestCase):
    'Test Cashier module'
    module = 'cashier'

    @with_transaction()
    def test_cashier(self):
        pool = Pool()
        Cashier = pool.get('cashier.cashier')
        CreditCardTerminal = pool.get('cashier.ccterminal')
        CreditCard = pool.get('cashier.ccterminal.creditcard')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CashierTestCase))
    return suite
