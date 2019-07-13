#This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from decimal import Decimal
from trytond.modules.log_action import LogActionMixin, write_log

__all__ = [
        'Close',
        'Document',
        'CreditCardTerminalMove',
        'CustomerReceivable',
        'CloseLog'
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
                    ('state', 'in', ['draft', 'quotation']),
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
    ccterminals = fields.One2Many('cashier.close.ccterminal.move',
        'close', 'Credit Card Terminals',
        states=_STATES, depends=_DEPENDS)
    ccterminal_amount = fields.Function(fields.Numeric('Credit Card amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_ccterminal_amount')
    customers_receivable = fields.One2Many(
        'cashier.close.customer_receivable', 'close', 'Customers Receivable',
        states=_STATES, depends=_DEPENDS)
    customer_receivable_amount = fields.Function(fields.Numeric(
            'Customers Receivable amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_customer_receivable_amount')
    cash = fields.Numeric('Cash', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES,
        depends=_DEPENDS + ['currency_digits'])
    diff = fields.Function(fields.Numeric('Diff',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_diff')
    logs = fields.One2Many('cashier.close.log_action', 'resource', 'Logs')

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
    def default_state():
        return 'draft'

    @staticmethod
    def default_cash():
        return Decimal('0.0')

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

    @fields.depends('ccterminals')
    def on_change_with_ccterminal_amount(self, name=None):
        res = Decimal('0.0')
        if self.ccterminals:
            for ccterminal in self.ccterminals:
                res += ccterminal.amount
        return res

    @fields.depends('customers_receivable')
    def on_change_with_customer_receivable_amount(self, name=None):
        res = Decimal('0.0')
        if self.customers_receivable:
            for cr in self.customers_receivable:
                res += cr.amount
        return res

    def _get_amount_val(self, amount):
        return amount if amount else Decimal('0.0')

    def get_diff(self, name):
        sale = self._get_amount_val(self.sale_amount)
        cash = self._get_amount_val(self.cash)
        document = self._get_amount_val(self.document_amount)
        ccterminal = self._get_amount_val(self.ccterminal_amount)
        cr = self._get_amount_val(self.customer_receivable_amount)

        res = sale - (cash + document + ccterminal + cr)
        return res

    def get_rec_name(self, name):
        if self.number:
            return self.number
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('number',) + tuple(clause[1:])]

    @classmethod
    def set_number(cls, closes):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('cashier.configuration')
        config = Config(1)
        for close in closes:
            if close.number:
                continue
            close.number = Sequence.get_id(config.close_seq.id)
        cls.save(closes)

    @classmethod
    def create(cls, vlist):
        closes = super(Close, cls).create(vlist)
        write_log('Created', closes)
        return closes

    @classmethod
    def delete(cls, closes):
        for close in closes:
            if close.state not in ['draft']:
                raise UserError(
                    gettext('cashier.close_delete_draft',
                        close=close.rec_name
                    ))
        super(Close, cls).delete(closes)

    @classmethod
    def _sales_to_invoice(cls, sales):
        Invoice = Pool().get('account.invoice')
        Shipment = Pool().get('stock.shipment.out')
        invoices = []
        for sale in sales:
            if sale.invoice_method != 'order' or \
                    sale.shipment_method != 'order':
                continue
            if sale.state != 'processing':
                continue
            if sale.shipments:
                if len(sale.shipments) > 1:
                    continue
                for ship in sale.shipments:
                    if ship.__class__.__name__ != 'stock.shipment.out':
                        continue
                    if ship.state != 'waiting':
                        continue
                    Shipment.assign([ship,])
                    Shipment.pack([ship,])
                    Shipment.done([ship,])

            for inv in sale.invoices:
                if inv.state == 'draft':
                    inv.invoice_date = sale.sale_date
                    inv.save()
                    invoices.append(inv)

        if invoices:
            Invoice.post(invoices)

    @classmethod
    def _get_receipt_line(cls, description, amount, account, party, invoice):
        pool = Pool()
        Line = pool.get('cash_bank.receipt.line')
        line = Line(
            party=party,
            invoice=invoice,
            account=account,
            amount=amount,
            description=description,
        )
        return line

    @classmethod
    def _get_documents(cls, documents):
        pool = Pool()
        Doc = pool.get('cash_bank.document')
        docs = []
        for doc in documents:
            d = Doc(
                type=doc.type,
                date=doc.date,
                reference=doc.reference,
                entity=doc.entity,
                amount=doc.amount
            )
            doc.cash_bank_document=d
            docs.append(d)
        return docs

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, closes):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = []
        for close in closes:
            sales += close.sales
        Sale.draft(sales)
        write_log('Draft', closes)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, closes):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = []
        for close in closes:
            if not close.sales:
                raise UserError(
                    gettext('cashier.close_no_sales',
                        close=close.rec_name,
                    ))
            sales += close.sales
        Sale.quote(sales)
        cls.set_number(closes)
        write_log('Confirmed', closes)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, closes):
        pool = Pool()
        Config = pool.get('cashier.configuration')
        Sale = pool.get('sale.sale')
        Receipt = pool.get('cash_bank.receipt')

        config = Config(1)
        receipts=[]

        for close in closes:
            Sale.confirm(close.sales)
            Sale.process(close.sales)
            cls._sales_to_invoice(close.sales)

            lines = []
            for sale in close.sales:
                invoice = sale.invoices[0]
                lines.append(
                    cls._get_receipt_line(
                        'Cashier Close', #TODO Improve, gettext
                        invoice.amount_to_pay,
                        invoice.account,
                        invoice.party,
                        invoice))

            for cct in close.ccterminals:
                lines.append(
                    cls._get_receipt_line(
                        'Cashier Close - ' + cct.creditcard.type, #TODO Improve, gettext
                        -cct.amount,
                        cct.ccterminal.cash_bank.payment_method.debit_account,
                        None, None))
                #TODO bank comision

            for rcv in close.customers_receivable:
                lines.append(
                    cls._get_receipt_line(
                        'Cashier Close', #TODO Improve, gettext
                        -rcv.amount,
                        rcv.party.account_receivable,
                        rcv.party,
                        None))

            if close.diff != 0:
                amount = close.diff
                if close.diff > 0:
                    amount = -amount
                lines.append(
                    cls._get_receipt_line(
                        'Cashier Close Diff', #TODO Improve, gettext
                        amount,
                        config.diff_account,
                        None, None))

            cash_receipt = Receipt(
                date=close.date,
                cash_bank=close.cashier.cash_bank_cash,
                type=close.cashier.receipt_type_cash,
                description='Cashier Close ' + close.number, #TODO Improve, gettext
                party=config.party_sale,
                cash=close.cash,
                documents=cls._get_documents(close.documents),
                lines=lines
            )
            cash_receipt.save()

            receipts.append(cash_receipt)

        Receipt.confirm(receipts)
        Receipt.post(receipts)
        write_log('Posted', closes)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, closes):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sales = []
        for close in closes:
            sales += close.sales
        Sale.cancel(sales)
        write_log('Cancelled', closes)


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
        'on_change_with_currency_digits')
    cash_bank_document = fields.Many2One('cash_bank.document',
        'Cash/Bank document', ondelete='RESTRICT',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
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

    @fields.depends('close', '_parent_close.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.close:
            return self.close.currency_digits
        return 2

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state


class CreditCardTerminalMove(ModelSQL, ModelView):
    "Cashier Close Credit Card Terminal Move"
    __name__ = "cashier.close.ccterminal.move"

    close = fields.Many2One('cashier.close',
        'Close', required=True)
    ccterminal = fields.Many2One('cashier.ccterminal',
        'Credit Card Terminal', required=True,
        domain=[
            ('cashier', '=', Eval(
                '_parent_close', {}).get(
                'cashier', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    creditcard = fields.Many2One('cashier.ccterminal.creditcard',
        'Credit Card', required=True,
        domain=[
            If(
                Bool(Eval('ccterminal')),
                [('ccterminal', '=', Eval('ccterminal'))],
                [('ccterminal', '=', -1)]
            ),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC + ['ccterminal'])
    amount = fields.Numeric('Amount', required=True,
        states=_STATES_DOC,
        digits=(16, Eval('currency_digits', 2)),
        depends=_DEPENDS_DOC + ['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @fields.depends('close', '_parent_close.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.close:
            return self.close.currency_digits
        return 2

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state


class CustomerReceivable(ModelSQL, ModelView):
    "Cashier Close Customer Receivable"
    __name__ = "cashier.close.customer_receivable"

    close = fields.Many2One('cashier.close',
        'Close', required=True)
    party = fields.Many2One('party.party',
        'Party', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount = fields.Numeric('Amount', required=True,
        states=_STATES_DOC,
        digits=(16, Eval('currency_digits', 2)),
        depends=_DEPENDS_DOC + ['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @fields.depends('close', '_parent_close.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.close:
            return self.close.currency_digits
        return 2

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state


class CloseLog(LogActionMixin):
    "Cashier Close Logs"
    __name__ = "cashier.close.log_action" 
    resource = fields.Many2One('cashier.close',
        'Close', ondelete='CASCADE', select=True)
