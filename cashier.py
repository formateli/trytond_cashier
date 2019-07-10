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
        'Credit Card Terminals')
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
    active = fields.Boolean('Active')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_active():
        return True


class CreditCardTerminal(ModelSQL, ModelView):
    'Credit Card Terminal'
    __name__ = 'cashier.ccterminal'
    cashier = fields.Many2One(
        'cashier.cashier', 'Cashier', required=True)
    name = fields.Char('Name', required=True, translate=True)
    cash_bank = fields.Many2One('cash_bank.cash_bank',
            'Bank', required=True,
            domain=[
                ('company', '=', Eval(
                    '_parent_cashier', {}).get(
                    'company', -1)),
                ('type', '=', 'bank')
            ])
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
    creditcards = fields.One2Many('cashier.ccterminal.creditcard',
        'ccterminal', 'Credit Cards Accepted')
    active = fields.Boolean('Active')

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
        ], 'Type', required=True)
    comission = fields.Numeric('Comission',
        digits=(16, Eval('comission_digits', 4)),
        depends=['comission_digits'])
    comission_digits = fields.Function(fields.Integer('Digits'),
        'get_comission_digits')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_comission_digits():
        return 4

    def get_comission_digits(self, name=None):
        return self.default_comission_digits
