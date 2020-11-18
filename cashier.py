#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool

__all__ = [
        'Cashier',
        'CreditCardTerminal',
        'CreditCard',
    ]


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
    ccterminals = fields.One2Many('cashier.ccterminal', 'cashier',
        'Credit Card Terminals',
        domain=[
            ('company', '=', Eval('company')),
            ['OR',
                ('cashier', '=', None),
                ('cashier', '=', Eval('id'))
            ]
        ], depends=['company', 'id'])
    cash_bank_cash = fields.Many2One('cash_bank.cash_bank',
            'Cash', required=True,
            domain=[
                ('company', '=', Eval('company')),
                ('type', '=', 'cash')
            ], depends=['company'])
    receipt_type_cash = fields.Many2One('cash_bank.receipt_type',
        'Receipt Type for Cash', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank_cash')),
                [('cash_bank', '=', Eval('cash_bank_cash'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'in')
        ], depends=['cash_bank_cash'])
    #TODO sale action
    #TODO diff action
    active = fields.Boolean('Active')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_active():
        return True

    @fields.depends('receipt_type_cash')
    def on_change_cash_bank_cash(self):
        self.receipt_type_cash = None


class CreditCardTerminal(ModelSQL, ModelView):
    'Credit Card Terminal'
    __name__ = 'cashier.ccterminal'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
        },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
        ], select=True)
    cashier = fields.Many2One('cashier.cashier', 'Cashier',
        ondelete='RESTRICT')
    name = fields.Char('Name', required=True, translate=True)
    cash_bank = fields.Many2One('cash_bank.cash_bank',
            'Bank', required=True,
            domain=[
                ('company', '=', Eval('company')),
                ('type', '=', 'bank')
            ], depends=['company'])
    creditcards = fields.One2Many('cashier.ccterminal.creditcard',
        'ccterminal', 'Credit Cards Accepted')
    active = fields.Boolean('Active')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_active():
        return True


class CreditCard(ModelSQL, ModelView):
    'Credit Card'
    __name__ = 'cashier.ccterminal.creditcard'
    ccterminal = fields.Many2One(
        'cashier.ccterminal', 'Credit Card Terminal', required=True)
    type = fields.Selection([
            ('visa', 'Visa'),
            ('master', 'Master Card'),
            ('amex', 'American Express'),
            ('debit', 'Debit'),
        ], 'Type', required=True)
    commission = fields.Numeric('Commission',
        digits=(16, Eval('commission_digits', 4)),
        depends=['commission_digits'])
    commission_digits = fields.Function(fields.Integer('Digits'),
        'get_commission_digits')
    account = fields.Many2One('account.account', "Expense Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval(
                '_parent_ccterminal', {}).get(
                'company', -1))
            ],
        depends=['commission'])
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_commission_digits():
        return 4

    def get_commission_digits(self, name=None):
        return self.default_commission_digits()

    def get_rec_name(self, name):
        if self.type:
            return self.type
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('type',) + tuple(clause[1:])]
