#This file is part of tryton-cashier module. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Not, Or, Bool
from trytond.i18n import gettext
from trytond.modules.currency.fields import Monetary
from trytond.exceptions import UserError
from decimal import Decimal
from trytond.modules.log_action import LogActionMixin, write_log


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
        domain=[
            ('company', '=', Eval('company')),
        ],
        states={
            'readonly': Or(Eval('state') != 'draft',
                            Eval('terminals')),
        }, depends=_DEPENDS + ['company', 'terminals'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': True,
        })
    number = fields.Char('Number', size=None, readonly=True, select=True)
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    sales = fields.One2Many('sale.sale', 'cashier_close', 'Sales',
        domain=[
            ('company', '=', Eval('company')),
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
        ], states=_STATES, depends=_DEPENDS + ['id', 'company'])
    sale_amount = fields.Function(Monetary('Sale amount',
            digits='currency', currency='currency'),
        'get_sale_amount')
    transfers = fields.One2Many('cash_bank.transfer',
        'cashier_close', 'Transfers',
        states={
            'readonly': True,
            },
        domain=[
            ('company', '=', Eval('company')),
            If(Eval('state').in_(['draft', 'confirmed']),
                [
                    ('state', 'in', ['draft']),
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
        ], depends=_DEPENDS + ['id', 'company'])
    terminals = fields.One2Many('cashier.close.terminal.move',
        'close', 'Money Terminals',
        states={
            'readonly': Or(Eval('state') != 'draft',
                Not(Eval('cashier'))),
        }, depends=_DEPENDS)
    terminal_amount = fields.Function(Monetary('Money terminals amount',
            digits='currency', currency='currency'),
        'get_terminal_amount')
    customers_receivable = fields.One2Many(
        'cashier.close.customer_receivable', 'close', 'Customers Receivable',
        states=_STATES, depends=_DEPENDS)
    customer_receivable_amount = fields.Function(Monetary(
            'Customers Receivable amount',
            digits='currency', currency='currency'),
        'get_customer_receivable_amount')
    customers_payable = fields.One2Many(
        'cashier.close.customer_payable', 'close', 'Customers Payable',
        states=_STATES, depends=_DEPENDS)
    customer_payable_amount = fields.Function(Monetary(
            'Customers Payable amount',
            digits='currency', currency='currency'),
        'get_customer_payable_amount')
    collected_in_advance = fields.One2Many(
        'cashier.close.advance', 'close', 'Collected in Advance',
        states=_STATES, depends=_DEPENDS)
    collected_in_advance_amount = fields.Function(Monetary(
            'Collected in Advance amount',
            digits='currency', currency='currency'),
        'get_collected_in_advance_amount')
    collected_in_advance_apply = fields.One2Many(
        'cashier.close.advance.apply', 'close',
        'Collected in Advance Applied',
        states=_STATES, depends=_DEPENDS)
    collected_in_advance_apply_amount = fields.Function(Monetary(
            'Collected in Advance Applied amount',
            digits='currency', currency='currency'),
        'get_collected_in_advance_apply_amount')
    diff = fields.Function(Monetary('Diff',
            digits='currency', currency='currency'),
        'get_diff')
    diff_cache = Monetary(
        'Diff Cache', digits='currency', currency='currency',
        readonly=True)
    total_affected = fields.Function(Monetary('Total Affected',
            digits='currency', currency='currency'),
        'get_total_affected')
    total_extra = fields.Function(Monetary('Total Extra',
            digits='currency', currency='currency'),
        'get_total_extra')
    total_collected = fields.Function(Monetary('Total Collected',
            digits='currency', currency='currency'),
        'get_total_collected')
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
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @fields.depends('sales',
        'terminals', 'customers_receivable',
        'customers_payable', 'collected_in_advance',
        'collected_in_advance_apply')
    def _get_amounts(self):
        self.sale_amount = self.get_sale_amount()
        self.terminal_amount = self.get_terminal_amount()
        self.customer_receivable_amount = \
            self.get_customer_receivable_amount()
        self.customer_payable_amount = \
            self.get_customer_payable_amount()
        self.collected_in_advance_amount = \
            self.get_collected_in_advance_amount()
        self.collected_in_advance_apply_amount = \
            self.get_collected_in_advance_apply_amount()
        self.total_affected = self.get_total_affected()
        self.total_extra = self.get_total_extra()
        self.total_collected = self.get_total_collected()
        self.diff = self.get_diff()

    @fields.depends(methods=['_get_amounts'])
    def on_change_sales(self):
        self._get_amounts()

    @fields.depends(methods=['_get_amounts'])
    def on_change_terminals(self):
        self._get_amounts()

    @fields.depends(methods=['_get_amounts'])
    def on_change_customers_receivable(self):
        self._get_amounts()

    @fields.depends(methods=['_get_amounts'])
    def on_change_customers_payable(self):
        self._get_amounts()

    @fields.depends(methods=['_get_amounts'])
    def on_change_collected_in_advance(self):
        self._get_amounts()

    @fields.depends(methods=['_get_amounts'])
    def on_change_collected_in_advance_apply(self):
        self._get_amounts()

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

    @fields.depends('terminals')
    def get_terminal_amount(self, name=None):
        return self._get_amount(self.terminals)

    @fields.depends('customers_receivable')
    def get_customer_receivable_amount(self, name=None):
        return self._get_amount(self.customers_receivable, 'amount_rp')

    @fields.depends('customers_payable')
    def get_customer_payable_amount(self, name=None):
        return self._get_amount(self.customers_payable, 'amount_rp')

    @fields.depends('collected_in_advance')
    def get_collected_in_advance_amount(self, name=None):
        return self._get_amount(self.collected_in_advance, 'amount_collected')

    @fields.depends('collected_in_advance_apply')
    def get_collected_in_advance_apply_amount(self, name=None):
        return self._get_amount(self.collected_in_advance_apply,
                'amount_apply_affected')

    def _get_amount_or_zero(self, amount):
        return amount if amount else Decimal('0.0')

    @fields.depends('sale_amount', 'total_affected')
    def get_diff(self, name=None):
        return self._get_amount_or_zero(self.sale_amount) - \
                self._get_amount_or_zero(self.total_affected)

    @fields.depends('customer_receivable_amount',
            'customer_payable_amount', 'collected_in_advance_amount',
            'collected_in_advance_apply_amount', 'terminal_amount')
    def get_total_affected(self, name=None):
        res = (
                self._get_amount_or_zero(self.terminal_amount) +
                self._get_amount_or_zero(self.customer_receivable_amount) +
                self._get_amount_or_zero(self.collected_in_advance_apply_amount)
            ) - (
                self._get_amount_or_zero(self.customer_payable_amount) +
                self._get_amount_or_zero(self.collected_in_advance_amount)
            )
        return res

    @fields.depends('terminals', 'collected_in_advance_apply')
    def get_total_extra(self, name=None):
        res = self._get_amount(self.terminals,
                'amount_ignore')
        res += self._get_amount(self.collected_in_advance_apply,
                'amount_apply_ignore')
        return res

    @fields.depends('total_affected', 'total_extra')
    def get_total_collected(self, name=None):
        return self._get_amount_or_zero(self.total_affected) + \
                self._get_amount_or_zero(self.total_extra)

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
        Config = pool.get('cashier.configuration')
        config = Config(1)
        for close in closes:
            if close.number:
                continue
            close.number = config.get_multivalue(
                'close_seq', company=close.company.id).get()
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
    def _get_receipt_line(cls, type_, description,
            amount, account, party, invoice,
            advance=None, advance_origin=None):
        pool = Pool()
        Line = pool.get('cash_bank.receipt.line')
        line = Line(
            type=type_,
            party=party,
            invoice=invoice,
            account=account,
            advance=advance,
            advance_origin=advance_origin,
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
    def _get_moneytype_docs(cls, id_, documents):
        docs = []
        for doc in documents:
            if doc[7] == id_:
                docs.append(doc)
        return docs

    @classmethod
    def _get_documents(cls, documents, create=True):
        docs = []

        if not create:
            for doc in documents:
                docs.append(doc[8])
            return docs

        pool = Pool()
        Doc = pool.get('cash_bank.document')

        for doc in documents:
            d = Doc(
                type=doc[2],
                party=doc[3],
                date=doc[4],
                reference=doc[5],
                entity=doc[6],
                amount=doc[0]
            )
            d.save()
            doc[8] = d
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
        write_log('Confirmed', closes, 'confirm')

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, closes):
        pool = Pool()
        Config = pool.get('cashier.configuration')
        ConfigCashBank = pool.get('cash_bank.configuration')
        Sale = pool.get('sale.sale')
        Receipt = pool.get('cash_bank.receipt')
        Transfer = pool.get('cash_bank.transfer')

        config = Config(1)
        config_cash_bank = ConfigCashBank(1)
        receipts = []

        for close in closes:
            Sale.confirm(close.sales)
            Sale.process(close.sales)
            with Transaction().set_context(_skip_warnings=True):
                # Evita la advertencia de pago anterior a la fecha
                # de la factura cuando se aplica pagos por adelantado.
                cls._sales_to_invoice(close.sales)

            msg = '[' + close.rec_name + '-' + close.cashier.rec_name + ']'

            cash = Decimal('0.0')
            documents = []
            lines = []
            money_plus = []

            for sale in close.sales:
                invoice = sale.invoices[0]
                lines.append(
                    cls._get_receipt_line(
                        'invoice_customer',
                        msg,
                        invoice.amount_to_pay,
                        invoice.account,
                        invoice.party,
                        invoice))

            for terminal in close.terminals:
                for moneytype in terminal.types:
                    is_document = moneytype.type.is_document
                    if is_document:
                        documents.append([
                            moneytype.amount_total,
                            moneytype.amount_ignore,
                            moneytype.type.cash_bank_document,
                            moneytype.party,
                            moneytype.date,
                            moneytype.reference,
                            moneytype.entity,
                            moneytype.id,
                            None  # cash_bank.document
                            ])
                    else:
                        cash += moneytype.amount_total
                    cls._add_money_plus(money_plus, moneytype)

            for rcv in close.customers_receivable:
                lines.append(
                    cls._get_receipt_line(
                        'move_line',
                        msg + ' ' + rcv.description if rcv.description else msg,
                        -rcv.amount_rp,
                        rcv.account,
                        rcv.party,
                        None))

            for rcv in close.customers_payable:
                lines.append(
                    cls._get_receipt_line(
                        'move_line',
                        msg + ' ' + rcv.description if rcv.description else msg,
                        rcv.amount_rp,
                        rcv.account,
                        rcv.party,
                        None))

            for cia in close.collected_in_advance:
                lines.append(
                    cls._get_receipt_line(
                        'advance_in_create',
                        msg + ' ' + cia.description if cia.description else msg,
                        cia.amount_collected,
                        cia.account,
                        cia.party,
                        None, None, cia.advance_origin))

            for cia in close.collected_in_advance_apply:
                lines.append(
                    cls._get_receipt_line(
                        'advance_in_apply',
                        msg + ' ' + cia.description if cia.description else msg,
                        -cia.amount_apply,
                        cia.advance.receipt_line.account,
                        cia.party,
                        None, cia.advance, None))

                if not cia.affect_close_total:
                    lines.append(
                        cls._get_receipt_line(
                            'move_line',
                            msg + ' ' + cia.description if cia.description else msg,
                            cia.amount_apply_ignore,
                            cia.account_alternate,
                            cia.party,
                            None, None, None))

            if close.diff != 0:
                lines.append(
                    cls._get_receipt_line(
                        'move_line',
                        msg + ' Diff',
                        -close.diff,
                        config.diff_account,
                        None, None))

            for mp in money_plus:
                lines.append(
                    cls._get_receipt_line(
                        'move_line',
                        msg + mp[2],
                        mp[1],
                        mp[0],
                        None, None))

            lines += cls._get_extra_lines(close)

            cash_receipt = Receipt(
                date=close.date,
                cash_bank=close.cashier.cash_bank_cash,
                type=close.cashier.receipt_type_cash,
                description=msg,
                party=close.company.party,
                cash=cash,
                documents=cls._get_documents(documents),
                lines=lines
            )
            cash_receipt.save()

            close.cash_bank_receipt = cash_receipt
            close.save()

            receipts.append(cash_receipt)

        Receipt.confirm(receipts)
        Receipt.post(receipts)
        write_log('Posted', closes, 'post')

        transfers = []

        for close in closes:
            close_msg = '[' + close.rec_name + '-' + \
                    close.cashier.name + ']'
            for terminal in close.terminals:
                msg = close_msg + '[' + terminal.terminal.name + ']'
                group = terminal.terminal.group
                cash = Decimal('0.0')
                docs = []
                for moneytype in terminal.types:
                    is_document = moneytype.type.is_document
                    if is_document:
                        docs += cls._get_moneytype_docs(
                                moneytype.id, documents)
                    else:
                        cash += moneytype.amount_total

                    if not group:
                        transfer = Transfer(
                            company=close.company,
                            date=close.date,
                            currency=close.currency,
                            cash_bank_from=close.cashier.cash_bank_cash,
                            type_from=close.cashier.receipt_type_cash_out,
                            cash_bank_to=terminal.terminal.cash_bank,
                            type_to=terminal.terminal.receipt_type,
                            cash=cash,
                            cashier_close=close,
                            cashier_close_terminal=terminal,
                            cashier_close_moneytype=moneytype,
                            description=msg + '[' + moneytype.type.type.name + ']',
                            documents=cls._get_documents(docs, False)
                            )
                        transfer.save()
                        transfers.append(transfer)
                        cash = Decimal('0.0')
                        docs = []

                if group:
                    transfer = Transfer(
                        company=close.company,
                        date=close.date,
                        currency=close.currency,
                        cash_bank_from=close.cashier.cash_bank_cash,
                        type_from=close.cashier.receipt_type_cash_out,
                        cash_bank_to=terminal.terminal.cash_bank,
                        type_to=terminal.terminal.receipt_type,
                        cash=cash,
                        cashier_close=close,
                        cashier_close_terminal=terminal,
                        cashier_close_moneytype=None,
                        description=msg,
                        documents=cls._get_documents(docs, False)
                        )
                    transfer.save()
                    transfers.append(transfer)

        Transfer.confirm(transfers)
        Transfer.post(transfers)

    @classmethod
    def _get_discounts_charges(cls, values, field, amount, digits, add_charge):
        if not values:
            return []
        if amount <= 0:
            return []

        res = []
        for value in values:
            dis_cha = getattr(value, field)
            if dis_cha.amount <= 0:
                continue

            disc = dis_cha.get_discount_amount(amount, digits)
            if disc == 0:
                continue

            res.append([
                value.account,
                disc,
                '[' + dis_cha.name + ']'
                ])

            if add_charge:
                res += cls._get_discounts_charges(
                        value.charges, 'charge', disc, digits, False)

        return res

    @classmethod
    def _get_discounts(cls, obj, amount, digits):
        return cls._get_discounts_charges(
                obj.discounts, 'discount', amount, digits, True)

    @classmethod
    def _add_money_plus(cls, money_plus, money_type):
        if money_type.amount_ignore <= 0:
            return

        for amount in money_type.amounts:
            if amount.amount_type.affect_close_total:
                continue
            money_plus.append([
                amount.amount_type.account_alternate,
                amount.amount,
                '[' + money_type.move.terminal.name + '] ' \
                    '[' + money_type.type.type.name + '] ' \
                    '[' + amount.amount_type.name + ']'
                ])

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
        write_log('Cancelled', closes, 'cancel')


class CloseDetailMixin(ModelSQL, ModelView):
    close = fields.Many2One('cashier.close',
        'Close', required=True, ondelete='CASCADE')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')
    party = fields.Many2One('party.party', 'Party',
        states={
            'required': Bool(Eval('party_required')),
            'invisible': Not(Bool(Eval('party_required'))),
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC + ['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    reference = fields.Char('Reference', size=None,
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    description = fields.Char('Description',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount = fields.Function(Monetary('Amount',
        digits='currency', currency='currency'),
        'get_amount')
    amount_ignore = fields.Function(Monetary('Ignored',
        digits='currency', currency='currency'),
        'get_amount_ignore')
    amount_total = fields.Function(Monetary('Total',
        digits='currency', currency='currency'),
        'get_amount_total')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_amount_ignore():
        return Decimal('0.0')

    @staticmethod
    def default_amount_total():
        return Decimal('0.0')

    @fields.depends('close', '_parent_close.currency')
    def on_change_with_currency(self, name=None):
        if self.close and self.close.currency:
            return self.close.currency.id

    @fields.depends('close', '_parent_close.state')
    def on_change_with_close_state(self, name=None):
        if self.close:
            return self.close.state

    @fields.depends('close', '_parent_close.company')
    def on_change_with_company(self, name=None):
        if self.close:
            return self.close.company.id

    @fields.depends('party')
    def on_change_with_party_required(self, name=None):
        pass

    def get_amount(self, name=None):
        pass

    def get_amount_ignore(self, name=None):
        pass

    @fields.depends('amount', 'amount_ignore')
    def get_amount_total(self, name=None):
        res = Decimal('0.0')
        if self.amount:
            res += self.amount
        if self.amount_ignore:
            res += self.amount_ignore
        return res


class MoneyTerminalMove(CloseDetailMixin):
    "Cashier Close Money Terminal Move"
    __name__ = "cashier.close.terminal.move"
    terminal = fields.Many2One('cashier.terminal',
        'Money Terminal', required=True,
        domain=[
            ('cashier', '=', Eval(
                '_parent_close', {}).get(
                'cashier', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    types = fields.One2Many('cashier.close.terminal.move.type',
        'move', 'Money Types',
        states=_STATES_DOC, depends=_DEPENDS_DOC)

    @fields.depends('terminal')
    def on_change_with_party_required(self, name=None):
        if self.terminal and self.terminal.receipt_type:
            return self.terminal.receipt_type.party_required

    def _get_amount(self, type_obj, check_ignore):
        res = Decimal('0.0')
        if not type_obj:
            return res
        for tp in type_obj:
            if check_ignore:
                if not tp or not tp.amount:
                    continue
                res += tp.amount
            else:
                if not tp or not tp.amount_ignore:
                    continue
                res += tp.amount_ignore
        return res

    @fields.depends('types')
    def on_change_types(self):
        self.amount = Decimal('0.0')
        self.amount_ignore = Decimal('0.0')
        self.amount_total = Decimal('0.0')
        if not self.types:
            return
        self.amount = self.get_amount()
        self.amount_ignore = self.get_amount_ignore()
        self.amount_total = self.get_amount_total()

    @fields.depends('types')
    def get_amount(self, name=None):
        return self._get_amount(self.types, True)

    @fields.depends('types')
    def get_amount_ignore(self, name=None):
        return self._get_amount(self.types, False)


class MoneyTerminalMoveType(ModelSQL, ModelView):
    "Cashier Close Money Terminal Move Type"
    __name__ = "cashier.close.terminal.move.type"
    move = fields.Many2One('cashier.close.terminal.move',
        'Terminal Move', required=True, ondelete='CASCADE')
    type = fields.Many2One('cashier.terminal.moneytype',
        'Money Type', required=True,
        domain=[
            ('terminal', '=', Eval(
                '_parent_move', {}).get(
                'terminal', -1)),
        ],
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    is_document = fields.Function(fields.Boolean('Is Document'),
        'on_change_with_is_document')
    date = fields.Date('Date',
        states={
            'invisible': Not(Bool(Eval('is_document'))),
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC + ['is_document'])
    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': Not(Bool(Eval('is_document'))),
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC + ['is_document'])
    reference = fields.Char('Reference', size=None,
        states={
            'invisible': Not(Bool(Eval('is_document'))),
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC + ['is_document'])
    entity = fields.Char('Entity', size=None,
        states={
            'invisible': Not(Bool(Eval('is_document'))),
            'readonly': Eval('close_state') != 'draft',
        }, depends=_DEPENDS_DOC + ['is_document'])
    amounts = fields.One2Many('cashier.close.terminal.move.amount',
        'type', 'Amount',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount = fields.Function(Monetary('Amount',
        digits='currency', currency='currency'),
        'on_change_with_amount')
    amount_ignore = fields.Function(Monetary('Ignored',
        digits='currency', currency='currency'),
        'on_change_with_amount_ignore')
    amount_total = fields.Function(Monetary('Total',
        digits='currency', currency='currency'),
        'on_change_with_amount_total')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @fields.depends('move', '_parent_move.close_state')
    def on_change_with_close_state(self, name=None):
        if self.move:
            return self.move.close_state

    @fields.depends('move', '_parent_move.currency')
    def on_change_with_currency(self, name=None):
        if self.move and self.move.currency:
            return self.move.currency.id

    @fields.depends('type')
    def on_change_with_is_document(self, name=None):
        if self.type:
            return self.type.is_document

    def _get_amount(self, amount_obj, check_ignore):
        res = Decimal('0.0')
        if not amount_obj:
            return res
        for mn in amount_obj:
            if not mn.amount_type:
                continue
            if mn.amount_type.affect_close_total and check_ignore:
                res += mn.amount
            elif not mn.amount_type.affect_close_total and not check_ignore:
                res += mn.amount
        return res

    @fields.depends('amounts')
    def on_change_with_amount(self, name=None):
        return self._get_amount(self.amounts, True)

    @fields.depends('amounts')
    def on_change_with_amount_ignore(self, name=None):
        return self._get_amount(self.amounts, False)

    @fields.depends('amounts', 'amount', 'amount_ignore')
    def on_change_with_amount_total(self, name=None):
        res = Decimal('0.0')
        if self.amount:
            res += self.amount
        if self.amount_ignore:
            res += self.amount_ignore
        return res


class MoneyTerminalMoveAmount(ModelSQL, ModelView):
    "Cashier Close Money Terminal Move Amount"
    __name__ = "cashier.close.terminal.move.amount"
    type = fields.Many2One('cashier.close.terminal.move.type',
        'Money Type', required=True, ondelete='CASCADE')
    amount_type = fields.Many2One('cashier.terminal.moneytype.amount',
        'Amount Type', required=True,
        domain=[
            ('moneytype', '=', Eval(
                '_parent_type', {}).get(
                'type', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount = Monetary('Amount', required=True,
        digits='currency', currency='currency',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    close_state = fields.Function(
        fields.Selection(STATES, 'Close State'),
        'on_change_with_close_state')

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @fields.depends('type', '_parent_type.close_state')
    def on_change_with_close_state(self, name=None):
        if self.type:
            return self.type.close_state

    @fields.depends('type', '_parent_type.currency')
    def on_change_with_currency(self, name=None):
        if self.type and self.type.currency:
            return self.type.currency.id


class CustomerReceivablePayableMixin(CloseDetailMixin):
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('context', {}).get('company', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount_rp = Monetary('Amount', required=True,
        digits='currency', currency='currency',
        states=_STATES_DOC, depends=_DEPENDS_DOC)

    @classmethod
    def __setup__(cls):
        super(CustomerReceivablePayableMixin, cls).__setup__()
        cls.party.states['invisible'] = False
        cls.party.states['required'] = True

    @staticmethod
    def _default_account(acc_type):
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config(1)
        account = getattr(config, acc_type)
        return account

    @staticmethod
    def _get_account(party, acc_type, acc_type_default):
        if party:
            account = getattr(party, acc_type)
            if not account:
                account = CustomerReceivablePayableMixin._default_account(
                        acc_type_default)
            if account:
                return account.id


class CustomerReceivable(CustomerReceivablePayableMixin):
    "Cashier Close Customer Receivable"
    __name__ = "cashier.close.customer_receivable"

    @fields.depends('party')
    def on_change_with_account(self, name=None):
        return CustomerReceivablePayableMixin._get_account(
                self.party,
                'account_receivable',
                'default_account_receivable')


class CustomerPayable(CustomerReceivablePayableMixin):
    "Cashier Close Customer Payable"
    __name__ = "cashier.close.customer_payable"

    @fields.depends('party')
    def on_change_with_account(self, name=None):
        return CustomerReceivablePayableMixin._get_account(
                self.party,
                'account_payable',
                'default_account_payable')


class ColletedInAdvance(CloseDetailMixin):
    "Cashier Close Collected in Advance"
    __name__ = "cashier.close.advance"
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('reconcile', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('context', {}).get('company', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    advance_origin = fields.Reference(
        'Origin', selection='get_advance_origin',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount_collected = Monetary('Amount', required=True,
        digits='currency', currency='currency',
        states=_STATES_DOC, depends=_DEPENDS_DOC)

    @classmethod
    def __setup__(cls):
        super(ColletedInAdvance, cls).__setup__()
        cls.party.states['invisible'] = False
        cls.party.states['required'] = True

    @staticmethod
    def default_account():
        pool = Pool()
        Config = pool.get('cash_bank.configuration')
        config = Config(1)
        account = config.default_collected_in_advanced_account
        if account:
            return account.id

    @classmethod
    def get_advance_origin(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        Advance = pool.get('cash_bank.advance')
        models = Advance._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]


class ColletedInAdvanceApply(CloseDetailMixin):
    "Cashier Close Collected in Advance Applied"
    __name__ = "cashier.close.advance.apply"
    advance = fields.Many2One('cash_bank.advance',
        'Advance', required=True,
        domain=[
            ('party', '=', Eval('party')),
            ('state', '=', 'pending'),
            ('type', '=', 'in'),
            ('company', '=', Eval('context', {}).get('company', -1)),
        ], states=_STATES_DOC, depends=_DEPENDS_DOC)
    amount_apply = Monetary('Amount Applied', required=True,
        digits='currency', currency='currency',
        states=_STATES_DOC, depends=_DEPENDS_DOC)
    affect_close_total = fields.Boolean('Affect Cashier Close Total',
            states=_STATES_DOC, depends=_DEPENDS_DOC)
    account_alternate = fields.Many2One('account.account', "Alternate Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1))
            ],
        states={
            'required': Not(Bool(Eval('affect_close_total'))),
            'invisible': Bool(Eval('affect_close_total')),
            'readonly': Eval('close_state') != 'draft'
            }, depends=_DEPENDS_DOC + ['affect_close_total'])
    amount_apply_affected = fields.Function(Monetary('Amount Apply Affected',
            digits='currency', currency='currency'),
        'on_change_with_amount_apply_affected')
    amount_apply_ignore = fields.Function(Monetary('Amount Apply Ignored',
            digits='currency', currency='currency'),
        'on_change_with_amount_apply_ignore')

    @classmethod
    def __setup__(cls):
        super(ColletedInAdvanceApply, cls).__setup__()
        cls.party.states['invisible'] = False
        cls.party.states['required'] = True
        cls.party.states['readonly'] = Bool(Eval('advance'))

    @staticmethod
    def default_affect_close_total():
        return True

    @fields.depends('advance')
    def on_change_with_amount_apply(self, name=None):
        if self.advance:
            return self.advance.amount_to_apply

    @fields.depends('amount_apply', 'affect_close_total')
    def on_change_with_amount_apply_affected(self, name=None):
        res = Decimal('0.0')
        if self.affect_close_total:
            if self.amount_apply:
                res = self.amount_apply
        return res

    @fields.depends('amount_apply', 'affect_close_total')
    def on_change_with_amount_apply_ignore(self, name=None):
        res = Decimal('0.0')
        if not self.affect_close_total:
            if self.amount_apply:
                res = self.amount_apply
        return res


class CloseLog(LogActionMixin):
    "Cashier Close Logs"
    __name__ = "cashier.close.log_action"
    resource = fields.Many2One('cashier.close',
        'Close', ondelete='CASCADE', select=True)
