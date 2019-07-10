#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from decimal import Decimal

__all__ = [
        'Close',
        'Document'
    ]

_STATES = {
    'readonly': Eval('state') != 'draft',
}

_STATES_DOC = {
    'readonly': Eval('close_state') != 'draft',
}

_DEPENDS = ['state']

_DEPENDS_DOC = ['close_state']

STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('posted', 'Posted'),
    ('cancel', 'Canceled'),
]


class Close(Workflow, ModelSQL, ModelView):
    "Cashier Close"
    __name__ = "cashier.close" 
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        select=True)
    cashier = fields.Many2One(
        'cashier.cashier', 'Cashier', required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': True,
        })
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    number = fields.Char('Number', size=None, readonly=True, select=True)
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    sales = fields.One2Many('sale.sale', 'cashier_close', 'Sales',
        domain=[
            If(Eval('state').in_(['draft', 'confirmed']),
                [
                    ('state', '=', 'draft'),
                    ['OR',
                        ('cashier_close', '=', None),
                        ('cashier_close', '=', Eval('id')),
                    ]
                ],
                [
                    ('state', '!=', 'draft'),
                    ('cashier_close', '=', Eval('id')),
                ],
            )
        ], states=_STATES, depends=_DEPENDS + ['id'])
    sale_amount = fields.Function(fields.Numeric('Sale amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_sale_amount')
    documents = fields.One2Many('cashier.close.document', 'close', 'Documents',
        states=_STATES, depends=_DEPENDS)
    document_amount = fields.Function(fields.Numeric('Document amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_document_amount')
    cash = fields.Numeric('Cash',
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES,
        depends=_DEPENDS + ['currency_digits'])
    logs = fields.One2Many('cashier.close.log', 'close',
        'Logs', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Close, cls).__setup__()
        cls._order[0] = ('id', 'DESC')

        cls._transitions |= set(
            (
                ('draft', 'confirmed'),
                ('confirmed', 'posted'),
                ('confirmed', 'cancel'),
                ('cancel', 'draft'),
            )
        )

        cls._buttons.update({
            'cancel': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'confirm': {
                'invisible': ~Eval('state').in_(['draft']),
                },
            'post': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'draft': {
                'invisible': ~Eval('state').in_(['cancel']),
                'icon': If(Eval('state') == 'cancel',
                    'tryton-clear', 'tryton-go-previous'),
                },
            })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('sales')
    def on_change_with_sale_amount(self, name=None):
        res = Decimal('0.0')
        if self.sales:
            for sale in self.sales:
                res += sale.total_amount
        return res

    @fields.depends('documents')
    def on_change_with_document_amount(self, name=None):
        res = Decimal('0.0')
        if self.documents:
            for document in self.documents:
                res += document.amount
        return res

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, closes):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, closes):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, closes):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, closes):
        pass


class Document(ModelSQL, ModelView):
    "Cahsier Close Document"
    __name__ = "cashier.close.document"
    close = fields.Many2One(
        'cashier.close', 'Close', required=True)
    type = fields.Many2One('cash_bank.document.type', 'Type',
        required=True,
        states=_STATES_DOC)
    amount = fields.Numeric('Amount', required=True,
        states=_STATES_DOC,
        digits=(16, Eval('currency_digits', 2)),
        depends=_DEPENDS_DOC + ['currency_digits'])
    date = fields.Date('Date', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    reference = fields.Char('Reference', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    entity = fields.Char('Entity', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    cash_bank_document = fields.Many2One('cash_bank.document',
        'Cash/Bank document', ondelete='RESTRICT',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    close_state = fields.Function(
        fields.Selection(STATES, 'Purchase State'),
        'on_change_with_close_state')

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_cashier_doc_amount', Check(t, t.amount > 0),
                'Amount must be greater than zero.'),
            ]

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_currency_digits():
        return Document._get_currency_digits()

    def get_currency_digits(self, name=None):
        return Document._get_currency_digits()

    @staticmethod
    def _get_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state


class CloseLog(ModelSQL, ModelView):
    'Cashier Close Log'
    __name__ = 'cashier.close.log'
    name = fields.Char('Action')
    date = fields.DateTime('Date', states={'readonly': True})
    user = fields.Many2One('res.user', 'User', readonly=True)
    close = fields.Many2One('cashier.close', 'Close', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(CloseLog, cls).__setup__()
        cls._order = [
                ('id', 'DESC'),
            ]

    @staticmethod
    def default_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()
