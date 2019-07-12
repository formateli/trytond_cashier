#This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.model import (
    ModelSingleton, ModelView, ModelSQL, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = ['Configuration', 'ConfigurationSequences']


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Cashier Configuration'
    __name__ = 'cashier.configuration'
    close_seq = fields.MultiValue(fields.Many2One(
        'ir.sequence', "Close Sequence", required=True,
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'casher.close'),
        ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'close_seq'}:
            return pool.get('cashier.configuration.sequences')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationSequences(ModelSQL, CompanyValueMixin):
    'Cashier Configuration Sequences'
    __name__ = 'cashier.configuration.sequences'
    close_seq = fields.Many2One(
        'ir.sequence', "Close Sequence", 
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cashier.close'),
        ])
