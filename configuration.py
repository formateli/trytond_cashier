#This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.model import (
    ModelSingleton, ModelView, ModelSQL, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = [
        'Configuration',
        'ConfigurationSequences',
        'ConfigurationParties'
        'ConfigurationAccounts',
    ]


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Cashier Configuration'
    __name__ = 'cashier.configuration'

    party_sale = fields.MultiValue(fields.Many2One(
        'party.party', "Party Sale", required=True))
    close_seq = fields.MultiValue(fields.Many2One(
        'ir.sequence', "Close Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cashier.close'),
        ]))
    diff_account = fields.MultiValue(fields.Many2One('account.account',
        'Diff Account', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
        ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'close_seq'}:
            return pool.get('cashier.configuration.sequences')
        if field in {'party_sale'}:
            return pool.get('cashier.configuration.parties')
        elif field == 'diff_account':
            return pool.get('cashier.configuration.accounts')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationSequences(ModelSQL, CompanyValueMixin):
    'Cashier Configuration Sequences'
    __name__ = 'cashier.configuration.sequences'
    close_seq = fields.Many2One(
        'ir.sequence', "Close Sequence", 
        domain=[
            ('company', 'in', [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cashier.close'),
        ])


class ConfigurationParties(ModelSQL, CompanyValueMixin):
    'Cashier Configuration Parties'
    __name__ = 'cashier.configuration.parties'
    party_sale = fields.Many2One(
        'party.party', "Party Sale", required=True)


class ConfigurationAccounts(ModelSQL, CompanyValueMixin):
    'Cashier Configuration Accounts'
    __name__ = 'cashier.configuration.accounts'
    diff_account = fields.Many2One('account.account',
        'Diff Account',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
        ])
