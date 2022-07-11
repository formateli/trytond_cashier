#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool, Not
from decimal import Decimal


class Cashier(ModelSQL, ModelView):
    'Cashier'
    __name__ = 'cashier.cashier'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
        },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
        ], select=True)
    name = fields.Char('Name', required=True, translate=True)
    terminals = fields.One2Many('cashier.terminal',
        'cashier', 'Money Terminals')
    cash_bank_cash = fields.Many2One('cash_bank.cash_bank',
            'Cash', required=True,
            domain=[
                ('company', '=', Eval('company')),
                ('type', '=', 'cash')
            ], depends=['company'])
    receipt_type_cash = fields.Many2One('cash_bank.receipt_type',
        'Receipt Type IN', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank_cash')),
                [('cash_bank', '=', Eval('cash_bank_cash'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'in')
        ], depends=['cash_bank_cash'])
    receipt_type_cash_out = fields.Many2One('cash_bank.receipt_type',
        'Receipt Type OUT', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank_cash')),
                [('cash_bank', '=', Eval('cash_bank_cash'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'out')
        ], depends=['cash_bank_cash'])
    active = fields.Boolean('Active')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_active():
        return True

    @fields.depends('cash_bank_cash')
    def on_chage_with_receipt_type_cash(self):
        return

    @fields.depends('cash_bank_cash')
    def on_change_with_receipt_type_cash_out(self):
        return


class MoneyTerminal(ModelSQL, ModelView):
    'Money Terminal'
    __name__ = 'cashier.terminal'
    cashier = fields.Many2One('cashier.cashier', 'Cashier',
        required=True, ondelete='CASCADE', select=True)
    name = fields.Char('Name', required=True, translate=True)
    cash_bank = fields.Many2One('cash_bank.cash_bank',
        'Bank', required=True,
        domain=[
            ('company', '=', Eval(
                '_parent_cashier', {}).get(
                'company', -1))
            ],
        depends=['cashier'])
    receipt_type = fields.Many2One('cash_bank.receipt_type',
        'Receipt Type', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank')),
                [('cash_bank', '=', Eval('cash_bank'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'in')
        ], depends=['cash_bank'])
    money_types = fields.One2Many('cashier.terminal.moneytype',
        'terminal', 'Money Types')
    group = fields.Boolean('Group')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    @fields.depends('receipt_type')
    def on_change_cash_bank(self):
        self.receipt_type = None


class TerminalMoneyType(ModelSQL, ModelView):
    'Terminal Money Type'
    __name__ = 'cashier.terminal.moneytype'
    terminal = fields.Many2One(
        'cashier.terminal', 'Money Terminal', required=True)
    type = fields.Many2One('cashier.terminal.moneytype.type',
        'Type', required=True)
    amounts = fields.One2Many('cashier.terminal.moneytype.amount',
        'moneytype', 'Amounts')
    is_document = fields.Boolean('Is Document')
    cash_bank_document = fields.Many2One('cash_bank.document.type',
        'Cash/Bank document',
        states={
            'required': Bool(Eval('is_document')),
            'invisible': Not(Bool(Eval('is_document'))),
            },
        depends=['is_document'])
    discounts = fields.One2Many('cashier.terminal.moneytype.discount',
        'moneytype', 'General Discounts')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    def get_rec_name(self, name):
        if self.type:
            return self.type.name
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('type.name',) + tuple(clause[1:])]

    @fields.depends('cash_bank_document')
    def on_change_is_document(self):
        self.cash_bank_document = None


class TerminalMoneyTypeAmount(ModelSQL, ModelView):
    'Terminal Money Type Amount'
    __name__ = 'cashier.terminal.moneytype.amount'
    moneytype = fields.Many2One('cashier.terminal.moneytype',
        'Terminal Money Type', required=True)
    name = fields.Char('Name', required=True, translate=True)
    discounts = fields.One2Many('cashier.terminal.moneytype.amount.discount',
        'moneytype_amount', 'Discounts')
    affect_close_total = fields.Boolean('Affect Cashier Close Total')
    account_alternate = fields.Many2One('account.account', "Alternate Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ],
        states={
            'required': Not(Bool(Eval('affect_close_total'))),
            'invisible': Bool(Eval('affect_close_total'))
            }, depends=['affect_close_total'])

    @staticmethod
    def default_affect_close_total():
        return True

    @fields.depends('affect_close_total')
    def on_change_with_account_alternate(self, name=None):
        return


class TerminalMoneyTypeDiscount(ModelSQL, ModelView):
    'Terminal Money Type Discount'
    __name__ = 'cashier.terminal.moneytype.discount'
    moneytype = fields.Many2One('cashier.terminal.moneytype',
        'Money type', required=True)
    discount = fields.Many2One('cashier.discount',
        'Discount', required=True)
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ])
    charges = fields.One2Many(
        'cashier.terminal.moneytype.discount.charge',
        'discount', 'Charges')


class TerminalMoneyTypeDiscountCharge(ModelSQL, ModelView):
    'Terminal Money Type Discount Charge'
    __name__ = 'cashier.terminal.moneytype.discount.charge'
    discount = fields.Many2One('cashier.terminal.moneytype.discount',
        'Discount', required=True)
    charge = fields.Many2One('cashier.discount',
        'Charge', required=True)
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ])


class TerminalMoneyTypeAmountDiscount(ModelSQL, ModelView):
    'Terminal Money Type Amount Discount'
    __name__ = 'cashier.terminal.moneytype.amount.discount'
    moneytype_amount = fields.Many2One('cashier.terminal.moneytype.amount',
        'Money type Amount', required=True)
    discount = fields.Many2One('cashier.discount',
        'Discount', required=True)
    account = fields.Many2One('account.account', "Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ])
    charges = fields.One2Many(
        'cashier.terminal.moneytype.amount.discount.charge',
        'discount', 'Charges')


class TerminalMoneyTypeAmountDiscountCharge(ModelSQL, ModelView):
    'Terminal Money Type Amount Discount Charge'
    __name__ = 'cashier.terminal.moneytype.amount.discount.charge'
    discount = fields.Many2One('cashier.terminal.moneytype.amount.discount',
        'Money type Amount', required=True)
    charge = fields.Many2One('cashier.discount',
        'Charge', required=True)
    account = fields.Many2One('account.account', "Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ])


class CashierDiscount(ModelSQL, ModelView):
    'Cashier Discount/Charge'
    __name__ = 'cashier.discount'
    name = fields.Char('Name', required=True, translate=True)
    type = fields.Selection([
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed'),
        ], 'Type', required=True)
    amount = fields.Numeric('Amount',
        digits=(16, Eval('amount_digits', 4)),
        depends=['amount_digits'])
    amount_digits = fields.Function(fields.Integer('Digits'),
        'get_amount_digits')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_amount_digits():
        return 4

    def get_amount_digits(self, name=None):
        return self.default_amount_digits()

    def get_discount_amount(self, amount, digits):
        res = Decimal('0.0')
        if self.type == 'fixed':
            res = self.amount
        elif self.type == 'percentage':
            res = amount * (self.amount / 100)

        exp = Decimal(str(10.0 ** -digits))
        return res.quantize(exp)


class MoneyTypeType(ModelSQL, ModelView):
    'Money Type'
    __name__ = 'cashier.terminal.moneytype.type'
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True
