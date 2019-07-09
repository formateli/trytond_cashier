

class Cashier(ModelSQL, ModelView, CompanyMultiValueMixin):
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
                ('company', '=', Eval('company'))
            ], depends=['company'])
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True


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
    name = fields.Char('Name', required=True, translate=True)
    cashier = fields.Many2One(
        'cashier.cashier', 'Cashier', required=True)
    payment_method = fields.Many2One('account.invoice.payment.method',
        'Account Payment Method', required=True,
        domain=[
            ('company', '=', Eval('company'))
        ], depends=['company'])
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
        'cashier.ccterminal', 'Credit card Terminal', required=True)
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



