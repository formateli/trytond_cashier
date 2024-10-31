#This file is part of tryton-cashier project. The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from decimal import Decimal


class Transfer(metaclass=PoolMeta):
    __name__ = 'cash_bank.transfer'
    cashier_close = fields.Many2One(
        'cashier.close', 'Cashier Close')
    cashier_close_terminal = fields.Many2One(
        'cashier.close.terminal.move', 'Cashier Close Terminal')
    cashier_close_moneytype = fields.Many2One(
        'cashier.close.terminal.move.type',
        'Cashier Close Terminal Money Type')

    def _get_cashier_close_transfer_data(self, moneytype):
        cash = Decimal('0.0')
        discounts = []

        if not moneytype.is_document:
            cash = moneytype.amount_total

        discounts += self.cashier_close._get_discounts(
                moneytype.type,
                moneytype.amount_total,
                self.cashier_close.currency.digits)

        for mnt in moneytype.amounts:
            discounts += self.cashier_close._get_discounts(
                    mnt.amount_type,
                    mnt.amount,
                    self.cashier_close.currency.digits)

        return cash, discounts 


    def _create_receipt_to(self, cash_bank, type_, transfer_account, docs):
        if not self.cashier_close_terminal:
            return super(Transfer, self)._create_receipt(
                cash_bank, self.cash, type_, transfer_account, docs)

        lines = []
        discounts = []
        close = self.cashier_close
        terminal = self.cashier_close_terminal
        msg = '[' + close.rec_name + '-' + close.cashier.name + \
                '][' + terminal.terminal.name + ']'
        total = Decimal('0.0')
        cash = Decimal('0.0')

        if self.cashier_close_moneytype:  # No grouping
            cash, discounts = self._get_cashier_close_transfer_data(
                    self.cashier_close_moneytype)
            total = self.cashier_close_moneytype.amount_total
        else:
            for moneytype in terminal.types:
                cs, disc = self._get_cashier_close_transfer_data(moneytype)
                cash += cs
                discounts += disc
                total += moneytype.amount_total

        for discount in discounts:
            if discount[1] > 0:
                lines.append(
                    close._get_receipt_line(
                        'move_line',
                        msg + discount[2],
                        -discount[1],
                        discount[0],
                        close.company.party,
                        None
                    )
                )
                lines.append(
                    close._get_receipt_line(
                        'move_line',
                        msg + discount[2],
                        discount[1],
                        terminal.terminal.cash_bank.account,
                        close.company.party,
                        None
                    )
                )

        if total > 0:
            lines.append(
                close._get_receipt_line(
                    'move_line',
                    'Transfer ' + msg,
                    total,
                    transfer_account,
                    close.company.party,
                    None
                )
            )

        receipt = self._new_receipt(cash_bank, cash, type_)
        receipt.documents = self._get_doc(receipt, docs)
        receipt.lines = lines 
        receipt.save()
        return receipt
