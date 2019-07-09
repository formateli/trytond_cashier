#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, If
from trytond.modules.product import price_digits

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
    name = fields.Char('Name', required=True, translate=True)
    cashier = fields.Many2One(
        'cashier.cashier', 'Cashier', required=True)
    payment_method = fields.Many2One('account.invoice.payment.method',
        'Account Payment Method', required=True,
        domain=[
            ('company', '=', Eval(
                '_parent_cashier', {}).get(
                'company', -1))
        ])
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
            digits=price_digits)
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True
