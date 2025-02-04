# This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.pool import Pool
import datetime
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart
from trytond.modules.cash_bank.tests import (
    create_bank_account, create_cash_bank, create_sequence,
    create_journal, create_fiscalyear)
from decimal import Decimal


class CashierTestCase(ModuleTestCase):
    'Test Cashier module'
    module = 'cashier'

    @with_transaction()
    def test_cashier(self):
        pool = Pool()
        Account = pool.get('account.account')
        ConfigCashBank = pool.get('cash_bank.configuration')
        Config = pool.get('cashier.configuration')
        Close = pool.get('cashier.close')
        TerminalMove = pool.get('cashier.close.terminal.move')
        TerminalMoveType = pool.get('cashier.close.terminal.move.type')
        TerminalMoveAmount = pool.get('cashier.close.terminal.move.amount')

        date = datetime.date.today()
        party = self._create_party('Sale Party', None, None)

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
            account_payable, = Account.search([
                    ('name', '=', 'Main Payable'),
                    ])

            product_category = self._create_product_category(
                    account_expense, account_revenue
                )
            product = self._create_product(product_category)

            journal = create_journal(company, 'journal_cash')

            _, bank_account = create_bank_account(
                party_bank=self._create_party('Party Bank',
                    account_receivable, account_payable),
                party_owner=company.party)

            cash_bank_seq = create_sequence(
                'Cash/Bank Sequence',
                'Cash and Bank Receipt',
                company)

            cash = create_cash_bank(
                company, 'Main Cash', 'cash',
                journal, account_cash, cash_bank_seq
            )

            bank = create_cash_bank(
                company, 'Main Bank', 'bank',
                journal, account_revenue, cash_bank_seq,
                bank_account
            )

            # Configuration

            config = Config(
                    close_seq=create_sequence('Cashier Closes',
                        'Cashier Closes', company),
                    diff_account=account_expense,
                )
            config.save()

            config_cash_bank = ConfigCashBank(
                    account_transfer=account_cash,
                )
            config_cash_bank.save()

            # Cashier

            cashier = self._create_cashier(cash, bank, account_expense)

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

            #TODO improve with several terminals

            # Add cash
            
            terminal_move = TerminalMove(
                    terminal=cashier.terminals[0],
                    types=[
                        TerminalMoveType(
                            type=cashier.terminals[0].money_types[0],
                            amounts=[
                                TerminalMoveAmount(
                                    amount_type=cashier.terminals[0].money_types[0].amounts[0],
                                    amount=Decimal('100.0')
                                ),
                                ]
                            )
                        ],
                )

            close.terminals=[terminal_move]
            close.save()

            self.assertEqual(close.terminal_amount, Decimal('100.0'))
            self.assertEqual(close.diff, Decimal('200.0'))

            Close.confirm([close])
            Close.post([close])

            self.assertEqual(len(close.transfers), 1)

            return

            # Add documents (Usually cheques)

            doc_type = self._create_document_type()

            close.documents = [
                    self._create_document(
                        party, doc_type, date, Decimal('10.0')),
                    self._create_document(
                        party, doc_type, date, Decimal('20.0')),
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

            party_1 = self._create_party(
                'Customer 1', account_receivable, account_payable)
            party_2 = self._create_party(
                'Customer 2', account_receivable, account_payable)

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

            # Add Customer Payable

            party_3 = self._create_party(
                'Customer 3', account_receivable, account_payable)

            close.customers_payable = [
                    self._create_customer_receivable(
                        party_3, Decimal('70.0'), payable=True),
                ]
            close.save()
            self.assertEqual(
                close.customer_payable_amount, Decimal('70.0'))
            self.assertEqual(close.diff, Decimal('160.0'))

            # Add ACH

            party_4 = self._create_party(
                'Customer 4', account_receivable, account_payable)

            close.achs = [
                    self._create_ach(party_4, date, Decimal('80.0'), bank),
                ]
            close.save()
            self.assertEqual(
                close.ach_amount, Decimal('80.0'))
            self.assertEqual(close.diff, Decimal('80.0'))

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
                self.assertEqual(sale.state, 'cancelled')

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
                self.assertEqual(sale.invoices[0].state, 'posted')

            # Case: Include cash

            sale_1 = self._create_sale(
                date, party, product, Decimal('742.49'))

            close = Close(
                cashier=cashier,
                date=date,
                sales=[sale_1],
                cash=Decimal('120.0'),
                ccterminals=[
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 0, Decimal('100.0')),
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 1, Decimal('200.0')),
                    ],
                customers_receivable=[
                    self._create_customer_receivable(
                        party_1, Decimal('120.0')),
                    ]
            )
            close.save()
            self.assertEqual(close.diff, Decimal('202.49'))

            Close.confirm([close])
            Close.post([close])

            # Case: Without cash

            sale_1 = self._create_sale(
                date, party, product, Decimal('742.49'))

            close = Close(
                cashier=cashier,
                date=date,
                sales=[sale_1],
                ccterminals=[
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 0, Decimal('100.0')),
                    self._create_ccterminal_move(
                        cashier.ccterminals[0], 1, Decimal('200.0')),
                    ],
                customers_receivable=[
                    self._create_customer_receivable(
                        party_1, Decimal('120.0')),
                    ]
            )
            close.save()
            self.assertEqual(close.diff, Decimal('322.49'))

            Close.confirm([close])
            Close.post([close])

            # Case: Just cash

            sale_1 = self._create_sale(
                date, party, product, Decimal('659.97'))

            close = Close(
                cashier=cashier,
                date=date,
                sales=[sale_1],
                cash=Decimal('1000.0')
            )
            close.save()
            self.assertEqual(close.diff, Decimal('-340.03'))

            Close.confirm([close])
            Close.post([close])

    def _create_customer_receivable(self, party, amount, payable=False):
        if payable:
            CR = Pool().get('cashier.close.customer_payable')
        else:
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

    def _create_document(self, party, doc_type, date, amount):
        Document = Pool().get('cashier.close.document')
        doc = Document(
            type=doc_type,
            party=party,
            date=date,
            amount=amount,
        )
        return doc

    def _create_document_type(self):
        Type = Pool().get('cash_bank.document.type')
        type_ = Type(name='Cheque')
        type_.save()
        return type_

    def _create_cashier(self, cash, bank, account_expense):
        Cashier = Pool().get('cashier.cashier')

        cashier = Cashier(
            name='Cashier 1',
            terminals=self._create_terminal(bank, account_expense),
            cash_bank_cash=cash,
            receipt_type_cash=cash.receipt_types[0],
            receipt_type_cash_out=cash.receipt_types[1],
        )
        cashier.save()
        return cashier

    def _create_terminal(self, bank, account_expense):
        CashierTerminal = Pool().get('cashier.terminal')

        terminal = CashierTerminal(
            name='Terminal 1',
            cash_bank=bank,
            receipt_type=bank.receipt_types[0],
            money_types=self._create_money_types(account_expense)
            )

        return [terminal]

    def _create_discount(self, name, type_, amount):
        Discount = Pool().get('cashier.discount')
        discount = Discount(
            name=name,
            type=type_,
            amount=amount
            )
        discount.save()
        return discount

    def _create_discount_2(self, model, discount, account):
        Discount = Pool().get(model)
        discount = Discount(
            discount=discount,
            account=account
            )
        return discount

    def _create_money_types(self, account_expense):
        pool = Pool()
        MoneyType = pool.get('cashier.terminal.moneytype.type')
        MoneyTerminalType = pool.get('cashier.terminal.moneytype')
        CashBankDocument = pool.get('cash_bank.document.type')

        discounts = [
            self._create_discount('Fixed', 'fixed', Decimal('0.5')),
            self._create_discount('Percentage 1', 'percentage', Decimal('15.0')),
            self._create_discount('Percentage 2', 'percentage', Decimal('25.0'))
            ]

        mt = MoneyType.search([('name', '=', 'Cash')])[0]

        mt_cash = MoneyTerminalType(
            type=mt,
            discounts=[
                self._create_discount_2(
                    'cashier.terminal.moneytype.discount',
                    discounts[0], account_expense),
                self._create_discount_2(
                    'cashier.terminal.moneytype.discount',
                    discounts[1], account_expense),
                ],
            amounts=[
                self._create_moneytype_amount(
                    'Base', None, True, None),
                ],
            )

        cb_doc = CashBankDocument.search([
                ('name', '=', 'Check')])[0]

        mt_cheque = MoneyTerminalType(
            type=mt,
            is_document=True,
            cash_bank_document=cb_doc,
            discounts=None,
            amounts=[
                self._create_moneytype_amount(
                    'Base', None, True, None),
                self._create_moneytype_amount(
                    'Tips', discounts[2], False,
                    account_expense)
                ],
            )


        return [mt_cash, mt_cheque]

    def _create_moneytype_amount(self, name, discount,
                affect_close_total, account_alternate):
        Amount = Pool().get('cashier.terminal.moneytype.amount')
        disc = None
        if discount:
            disc = [self._create_discount_2(
                    'cashier.terminal.moneytype.amount.discount',
                    discount, account_alternate)]

        amount = Amount(
            name=name,
            discounts=disc,
            affect_close_total=affect_close_total,
            account_alternate=account_alternate
            )
        return amount

    def _create_sale(self, date, party, product, amount):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')

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
    def _create_party(cls, name, receivable, payable):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        addr = Address(
            name=name,
        )
        party = Party(
            name=name,
            account_receivable=receivable,
            account_payable=payable,
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


del ModuleTestCase
