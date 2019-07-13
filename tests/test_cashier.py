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

        date = datetime.date.today()
        party = self._create_party('Sale Party', None)

        company = create_company()
        with set_company(company):
            create_chart(company)
            create_fiscalyear(company)

            account_cash, = Account.search([
                    ('name', '=', 'Main Cash'),
                    ])
            account_revenue, = Account.search([
                    ('name', '=', 'Main Revenue'),
                    ])
            account_expense, = Account.search([
                    ('name', '=', 'Main Expense'),
                    ])
            account_receivable, = Account.search([
                    ('name', '=', 'Main Receivable'),
                    ])

            product_category = self._create_product_category(
                    account_expense, account_revenue
                )
            product = self._create_product(product_category)

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
                    party_sale=party,
                    close_seq=create_sequence('Cashier Close Seq',
                        'cashier.close', company),
                    diff_account=account_expense,
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
            self.assertEqual(close.diff, Decimal('300.0'))

            # Add documents (Usually cheques)

            doc_type = self._create_document_type()

            close.documents = [
                    self._create_document(doc_type, date, Decimal('10.0')),
                    self._create_document(doc_type, date, Decimal('20.0')),
                ]
            close.save()
            self.assertEqual(close.document_amount, Decimal('30.0'))
            self.assertEqual(close.diff, Decimal('270.0'))

            # Add Credit Card Terminal Move

            close.ccterminals = [
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 0, Decimal('30.0')),
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 1, Decimal('40.0')),
                ]
            close.save()
            self.assertEqual(close.ccterminal_amount, Decimal('70.0'))
            self.assertEqual(close.diff, Decimal('200.0'))

            # Add Customer Receivable

            party_1 = self._create_party('Customer 1', account_receivable)
            party_2 = self._create_party('Customer 2', account_receivable)

            close.customers_receivable = [
                    self._create_customer_receivable(
                        party_1, Decimal('50.0')),
                    self._create_customer_receivable(
                        party_2, Decimal('60.0')),
                ]
            close.save()
            self.assertEqual(
                close.customer_receivable_amount, Decimal('110.0'))
            self.assertEqual(close.diff, Decimal('90.0'))

            # Confirm Close
            Close.confirm([close])
            self.assertEqual(close.number, '1')
            self.assertEqual(close.state, 'confirmed')
            for sale in close.sales:
                self.assertEqual(sale.cashier_close.id, close.id)
                self.assertEqual(sale.state, 'quotation')

            # Cancel Close
            Close.cancel([close])
            self.assertEqual(close.state, 'cancel')
            for sale in close.sales:
                self.assertEqual(sale.state, 'cancel')

            # Draft Close
            Close.draft([close])
            self.assertEqual(close.state, 'draft')
            for sale in close.sales:
                self.assertEqual(sale.state, 'draft')

            # Confirm again
            Close.confirm([close])

            # Post Close
            Close.post([close])
            self.assertEqual(close.state, 'posted')
            for sale in close.sales:
                self.assertEqual(sale.invoices[0].state, 'paid')


    def _create_customer_receivable(self, party, amount):
        CR = Pool().get('cashier.close.customer_receivable')
        cr = CR(
            party=party,
            amount=amount,
        )
        return cr

    def _create_ccterminal_move(self, ccterminal, creditcard, amount):
        Move = Pool().get('cashier.close.ccterminal.move')
        move = Move(
            ccterminal=ccterminal,
            creditcard=ccterminal.creditcards[creditcard],
            amount=amount,
        )
        return move

    def _create_document(self, doc_type, date, amount):
        Document = Pool().get('cashier.close.document')
        doc = Document(
            type=doc_type,
            date=date,
            amount=amount,
        )
        return doc

    def _create_document_type(self):
        Type = Pool().get('cash_bank.document.type')
        type_ = Type(name='Cheque')
        type_.save()
        return type_

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
    def _create_party(cls, name, account):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        addr = Address(
            name=name,
        )
        party = Party(
            name=name,
            account_receivable=account,
            addresses=[addr,],
        )
        party.save()
        return party

    @classmethod
    def _create_product_category(cls, account_expense, account_revenue):
        pool = Pool()
        Catrgory = pool.get('product.category')
        category=Catrgory(
            name='Product Category',
            accounting=True,
            account_expense=account_expense,
            account_revenue=account_revenue,
        )
        category.save()
        return category

    @classmethod
    def _create_product(cls, product_category):
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
            account_category=product_category,
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
