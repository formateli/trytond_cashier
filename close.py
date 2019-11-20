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
        'Ach',
        'CreditCardTerminalMove',
        'CustomerReceivable',
        'CustomerPayable',
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
    cashier = fields.Many2One('cashier.cashier', 'Cashier', required=True,
        states=_STATES, depends=_DEPENDS)
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
        'get_sale_amount')
    documents = fields.One2Many('cashier.close.document', 'close', 'Documents',
        states=_STATES, depends=_DEPENDS)
    document_amount = fields.Function(fields.Numeric('Document amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_document_amount')
    achs = fields.One2Many('cashier.close.ach', 'close', 'ACH',
        states=_STATES, depends=_DEPENDS)
    ach_amount = fields.Function(fields.Numeric('ACH amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_ach_amount')
    ccterminals = fields.One2Many('cashier.close.ccterminal.move',
        'close', 'Credit Card Terminals',
        states=_STATES, depends=_DEPENDS)
    ccterminal_amount = fields.Function(fields.Numeric('Credit Card amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_ccterminal_amount')
    customers_receivable = fields.One2Many(
        'cashier.close.customer_receivable', 'close', 'Customers Receivable',
        states=_STATES, depends=_DEPENDS)
    customer_receivable_amount = fields.Function(fields.Numeric(
            'Customers Receivable amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_customer_receivable_amount')
    customers_payable = fields.One2Many(
        'cashier.close.customer_payable', 'close', 'Customers Payable',
        states=_STATES, depends=_DEPENDS)
    customer_payable_amount = fields.Function(fields.Numeric(
            'Customers Payable amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_customer_payable_amount')
    cash = fields.Numeric('Cash', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES,
        depends=_DEPENDS + ['currency_digits'])
    diff = fields.Function(fields.Numeric('Diff',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_diff')
    note = fields.Text('Notes', size=None)
    cash_bank_receipt = fields.Many2One('cash_bank.receipt',
        'Receipt', readonly=True)
    logs = fields.One2Many('cashier.close.log_action', 'resource', 'Logs',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(Close, cls).__setup__()
        cls._order[0] = ('number', 'DESC')

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

    @fields.depends('cash', 'sales', 'documents', 'achs',
        'ccterminals', 'customers_receivable',
        'customers_payable')
    def on_change_cash(self):
        self.sale_amount = self.get_sale_amount()
        self.document_amount = self.get_document_amount()
        self.ach_amount = self.get_ach_amount()
        self.ccterminal_amount = self.get_ccterminal_amount()
        self.customer_receivable_amount = \
            self.get_customer_receivable_amount()
        self.customer_payable_amount = \
            self.get_customer_payable_amount()
        self.diff = self.get_diff()

    @fields.depends(methods=['on_change_cash'])
    def on_change_sales(self):
        self.on_change_cash()

    @fields.depends(methods=['on_change_cash'])
    def on_change_documents(self):
        self.on_change_cash()

    @fields.depends(methods=['on_change_cash'])
    def on_change_achs(self):
        self.on_change_cash()

    @fields.depends(methods=['on_change_cash'])
    def on_change_ccterminals(self):
        self.on_change_cash()

    @fields.depends(methods=['on_change_cash'])
    def on_change_customers_receivable(self):
        self.on_change_cash()

    @fields.depends(methods=['on_change_cash'])
    def on_change_customers_payable(self):
        self.on_change_cash()

    def _get_amount(self, field, name='amount'):
        res = Decimal('0.0')
        if field:
            for f in field:
                amount = getattr(f, name)
                if amount:
                    res += amount
        return res

    @fields.depends('sales')
    def get_sale_amount(self, name=None):
        return self._get_amount(self.sales, 'total_amount')

    @fields.depends('documents')
    def get_document_amount(self, name=None):
        return self._get_amount(self.documents)

    @fields.depends('achs')
    def get_ach_amount(self, name=None):
        return self._get_amount(self.achs)

    @fields.depends('ccterminals')
    def get_ccterminal_amount(self, name=None):
        return self._get_amount(self.ccterminals)

    @fields.depends('customers_receivable')
    def get_customer_receivable_amount(self, name=None):
        return self._get_amount(self.customers_receivable)

    @fields.depends('customers_payable')
    def get_customer_payable_amount(self, name=None):
        return self._get_amount(self.customers_payable)

    def _get_amount_or_zero(self, amount):
        return amount if amount else Decimal('0.0')

    @fields.depends('cash', 'document_amount', 'ach_amount',
            'ccterminal_amount', 'customer_receivable_amount',
            'customer_payable_amount')
    def get_diff(self, name=None):
        res = (
                self._get_amount_or_zero(self.sale_amount) + 
                self._get_amount_or_zero(self.customer_payable_amount)
            ) - (
                self._get_amount_or_zero(self.cash) +
                self._get_amount_or_zero(self.document_amount) +
                self._get_amount_or_zero(self.ach_amount) +
                self._get_amount_or_zero(self.ccterminal_amount) +
                self._get_amount_or_zero(self.customer_receivable_amount)
            )
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
                write_log('Delete attempt', [close])
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
    def _get_extra_lines(cls, close):
        ''' 
        To extend with other modules.
        It must return a list of cash_bank.receipt.line
        '''
        return []

    @classmethod
    def _get_documents(cls, documents):
        pool = Pool()
        Doc = pool.get('cash_bank.document')
        docs = []
        for doc in documents:
            d = Doc(
                type=doc.type,
                party=doc.party,
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
        write_log('Confirmed', closes, key='confirm')

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, closes):
        pool = Pool()
        Config = pool.get('cashier.configuration')
        ConfigCashBank = pool.get('cash_bank.configuration')
        Sale = pool.get('sale.sale')
        Receipt = pool.get('cash_bank.receipt')

        config = Config(1)
        config_cash_bank = ConfigCashBank(1)
        receipts = []
        ach_receipts = []

        for close in closes:
            Sale.confirm(close.sales)
            Sale.process(close.sales)
            cls._sales_to_invoice(close.sales)

            msg = 'Cashier Close ' + close.rec_name

            lines = []
            for sale in close.sales:
                invoice = sale.invoices[0]
                lines.append(
                    cls._get_receipt_line(
                        msg,
                        invoice.amount_to_pay,
                        invoice.account,
                        invoice.party,
                        invoice))

            for cct in close.ccterminals:
                lines.append(
                    cls._get_receipt_line(
                        msg + ' - ' + cct.creditcard.type,
                        -cct.amount,
                        cct.ccterminal.cash_bank.account,
                        None, None))
                if cct.commission and cct.creditcard.account:
                    commission = cct.commission_amount
                    if commission:
                        lines.append(
                            cls._get_receipt_line(
                                msg + ' - ' + cct.creditcard.type + ' commission',
                                -commission,
                                cct.creditcard.account,
                                None, None))
                        lines.append(
                            cls._get_receipt_line(
                                msg + ' - ' + cct.creditcard.type + ' commission',
                                commission,
                                cct.ccterminal.cash_bank.account,
                                None, None)) 

            for rcv in close.customers_receivable:
                lines.append(
                    cls._get_receipt_line(
                        msg + ' ' + rcv.description if rcv.description else '',
                        -rcv.amount,
                        rcv.party.account_receivable,
                        rcv.party,
                        None))

            for rcv in close.customers_payable:
                lines.append(
                    cls._get_receipt_line(
                        msg + ' ' + rcv.description if rcv.description else '',
                        rcv.amount,
                        rcv.party.account_payable,
                        rcv.party,
                        None))

            for ach in close.achs:
                lines.append(
                    cls._get_receipt_line(
                        msg + ' ' + ach.full_description(),
                        -ach.amount,
                        config_cash_bank.account_transfer,
                        None, None))

                ach_receipt = Receipt(
                    date=ach.date,
                    cash_bank=ach.bank,
                    type=ach.receipt_type,
                    reference=ach.reference,
                    description=msg + ' ' + ach.full_description(),
                    party=ach.party,
                    cash=ach.amount,
                    lines=[
                        cls._get_receipt_line(
                            msg + ' ' + ach.full_description(),
                            ach.amount,
                            config_cash_bank.account_transfer,
                            None,
                            None)
                    ]
                )
                ach_receipt.save()
                ach.bank_receipt = ach_receipt
                ach.save()
                ach_receipts.append(ach_receipt)

            if close.diff != 0:
                lines.append(
                    cls._get_receipt_line(
                        msg + ' Diff',
                        -close.diff,
                        config.diff_account,
                        None, None))

            lines += cls._get_extra_lines(close)

            cash_receipt = Receipt(
                date=close.date,
                cash_bank=close.cashier.cash_bank_cash,
                type=close.cashier.receipt_type_cash,
                description=msg,
                party=config.party_sale,
                cash=close.cash,
                documents=cls._get_documents(close.documents),
                lines=lines
            )
            cash_receipt.save()

            close.cash_bank_receipt = cash_receipt
            close.save()

            receipts.append(cash_receipt)

        Receipt.confirm(receipts)
        Receipt.post(receipts)
        if ach_receipts:
            Receipt.confirm(ach_receipts)
            Receipt.post(ach_receipts)
            write_log('ACH Bank receipts Posted', closes)
        write_log('Posted', closes, key='post')

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
        write_log('Cancelled', closes, key='cancel')


class CloseDetailMixin(ModelSQL, ModelView):
    close = fields.Many2One('cashier.close',
        'Close', required=True, ondelete='CASCADE')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')
    amount = fields.Numeric('Amount', required=True,
        states=_STATES_DOC,
        digits=(16, Eval('currency_digits', 2)),
        depends=_DEPENDS_DOC + ['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('close', '_parent_close.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.close:
            return self.close.currency_digits
        return 2

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state

    @fields.depends('close', '_parent_close.company')
    def on_change_with_company(self, name=None):
        if self.close:
            return self.close.company.id


class Document(CloseDetailMixin):
    "Cahsier Close Document"
    __name__ = "cashier.close.document"
    type = fields.Many2One('cash_bank.document.type', 'Type',
        required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': True,
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC)
    date = fields.Date('Date', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    reference = fields.Char('Reference', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    entity = fields.Char('Entity', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    cash_bank_document = fields.Many2One('cash_bank.document',
        'Cash/Bank document', ondelete='RESTRICT',
        states=_STATES_DOC, depends=_DEPENDS_DOC)

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_cashier_doc_amount', Check(t, t.amount > 0),
                'Amount must be greater than zero.'),
            ]


class CreditCardTerminalMove(CloseDetailMixin):
    "Cashier Close Credit Card Terminal Move"
    __name__ = "cashier.close.ccterminal.move"
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
    commission = fields.Numeric('Commission',
        states={'readonly': True},
        digits=(16, Eval('commission_digits', 4)),
        depends=['commission_digits'])
    commission_amount = fields.Function(fields.Numeric('Commission amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_commission_amount')
    commission_digits = fields.Function(fields.Integer('commission Digits'),
        'on_change_with_commission_digits')

    @fields.depends('creditcard')
    def on_change_with_commission_digits(self, name=None):
        if self.creditcard:
            return self.creditcard.commission_digits
        return 4

    def get_commission_amount(self, name=None):
        if self.amount and self.commission:
            result = self.amount * (self.commission / 100)
            exp = Decimal(str(10.0 ** -self.currency_digits))
            return result.quantize(exp)

    @fields.depends('close', '_parent_close.state', 'amount',
        'commission', 'currency_digits')
    def on_change_amount(self):
        self.commission_amount = None
        if self.amount and self.commission:
            self.currency_digits = self.on_change_with_currency_digits()
            self.commission_amount = self.get_commission_amount()

    @fields.depends('amount', 'creditcard')
    def on_change_creditcard(self):
        self.commission = None
        self.commission_amount = None
        if self.creditcard:
            self.commission = self.creditcard.commission
            self.on_change_amount()

    @fields.depends('amount')
    def on_change_ccterminal(self):
        self.creditcard = None
        self.on_change_creditcard()


class Ach(CloseDetailMixin):
    "Cashier Close ACH"
    __name__ = "cashier.close.ach"
    party = fields.Many2One('party.party',
        'Party', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    date = fields.Date('Date', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    reference = fields.Char('Reference', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    description = fields.Char('Description',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    bank = fields.Many2One('cash_bank.cash_bank',
            'Bank', required=True,
            domain=[
                ('company', '=', Eval(
                    '_parent_close', {}).get(
                    'company', -1)),
                ('type', '=', 'bank')
            ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    receipt_type = fields.Many2One('cash_bank.receipt_type',
        'Receipt Type', required=True,
        domain=[
            If(
                Bool(Eval('bank')),
                [('cash_bank', '=', Eval('bank'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'in')
        ], states=_STATES_DOC, depends=_DEPENDS_DOC + ['bank'])
    bank_receipt = fields.Many2One('cash_bank.receipt',
        'Receipt', readonly=True)

    @fields.depends('receipt_type')
    def on_change_bank(self):
        self.receipt_type = None

    def full_description(self):
        val = 'ACH ' + self.bank.rec_name + ' - ' + self.party.rec_name
        val += ': Ref: ' + self.reference if self.reference else ''
        val += ' - ' + self.description if self.description else ''
        return val


class CustomerReceivablePayableMixin(CloseDetailMixin):
    party = fields.Many2One('party.party',
        'Party', required=True,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    description = fields.Char('Description',
        states=_STATES_DOC, depends=_DEPENDS_DOC)


class CustomerReceivable(CustomerReceivablePayableMixin):
    "Cashier Close Customer Receivable"
    __name__ = "cashier.close.customer_receivable"


class CustomerPayable(CustomerReceivablePayableMixin):
    "Cashier Close Customer Payable"
    __name__ = "cashier.close.customer_payable"


class CloseLog(LogActionMixin):
    "Cashier Close Logs"
    __name__ = "cashier.close.log_action" 
    resource = fields.Many2One('cashier.close',
        'Close', ondelete='CASCADE', select=True)
