# This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.pool import Pool
import datetime
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.modules.cash_bank.tests import (
    create_cash_bank, create_sequence,
    create_payment_method, create_fiscalyear)
from decimal import Decimal


class CashierTestCase(ModuleTestCase):
    'Test Cashier module'
    module = 'cashier'

    @with_transaction()
    def test_cashier(self):
        pool = Pool()
        Account = pool.get('account.account')
        Config = Pool().get('cashier.configuration')
        Close = pool.get('cashier.close')
        Document = pool.get('cashier.close.document')

        date = datetime.date.today()
        product = self._create_product()
        party = self._create_party()

        company = create_company()
        with set_company(company):
            create_chart(company)
            create_fiscalyear(company)

            account_cash, = Account.search([
                    ('name', '=', 'Main Cash'),
                    ])

            payment_method = create_payment_method(
                company, 'journal_cash', account_cash)

            cash_bank_seq = create_sequence(
                'Cash/Bank Sequence',
                'cash_bank.receipt',
                company)

            cash = create_cash_bank(
                company, 'Main Cash', 'cash',
                payment_method, cash_bank_seq
            )

            bank = create_cash_bank(
                company, 'Main Bank', 'bank',
                payment_method, cash_bank_seq
            )

            # Configuration

            config = Config(
                    close_seq=create_sequence('Cashier Close Seq',
                        'cashier.close', company),
                )
            config.save()

            # Cashier

            cashier = self._create_cashier(cash, bank)

            # Cashier Close

            sale_1 = self._create_sale(
                date, party, product, Decimal('100.0'))    
            sale_2 = self._create_sale(
                date, party, product, Decimal('200.0'))

            close = Close(
                cashier=cashier,
                date=date,
                sales=[sale_1, sale_2],
            )
            close.save()
            self.assertEqual(close.sale_amount, Decimal('300.0'))

            Close.confirm([close])
            self.assertEqual(close.number, '1')
            self.assertEqual(close.state, 'confirmed')
            for sale in close.sales:
                self.assertEqual(sale.cashier_close.id, close.id)
                self.assertEqual(sale.state, 'confirmed')

    def _create_cashier(self, cash, bank):
        Cashier = Pool().get('cashier.cashier')

        cashier = Cashier(
            name='Cashier 1',
            ccterminals=self._create_ccterminal(bank),
            cash_bank_cash=cash,
            receipt_type_cash=cash.receipt_types[0],
        )
        cashier.save()
        return cashier

    def _create_ccterminal(self, bank):
        CreditCardTerminal = Pool().get('cashier.ccterminal')

        creditcards = []
        creditcards.append(
            self._create_creditcard('visa', Decimal('0.1')))
        creditcards.append(
            self._create_creditcard('master', Decimal('0.2')))

        ccterminal = CreditCardTerminal(
            name='Terminal Bank 1',
            cash_bank=bank,
            receipt_type=bank.receipt_types[0],
            creditcards=creditcards,
        )

        return [ccterminal,]

    def _create_creditcard(self, type_, comission):
        CreditCard = Pool().get('cashier.ccterminal.creditcard')
        cc = CreditCard(
            type=type_,
            comission=comission
        )
        return cc

    def _create_sale(self, date, party, product, amount):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')
        Party = pool.get('party.party')

        line = Line()
        line.product = product
        line.quantity = 1.0
        line.unit = product.default_uom
        line.unit_price = amount

        sale = Sale()
        sale.sale_date = date
        sale.party = party
        sale.invoice_address = party.addresses[0]
        sale.shipment_party = party
        sale.shipment_address = party.addresses[0]
        sale.lines = [line,]
        sale.save()
        return sale

    @classmethod
    def _create_party(cls):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        addr = Address(
            name='Address',
        )
        party = Party(
            name='Sale Party',
            addresses=[addr,],
        )
        party.save()
        return party

    @classmethod
    def _create_product(cls):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        uom = cls._get_uom('Unit')

        template=Template(
            name='Sale Product',
            default_uom=uom,
            type='service',
            salable=True,
            sale_uom=uom,
        )
        template.save()

        product = Product(
            template=template,
        )
        product.save()
        return product

    @classmethod
    def _get_uom(cls, name):
        Uom = Pool().get('product.uom')
        # Kilogram, Gram, Unit
        uom = Uom.search([('name', '=', name)])[0]
        return uom


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CashierTestCase))
    return suite
