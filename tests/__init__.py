# This file is part of Tryton cashier module. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.cashier.tests.test_cashier import suite
except ImportError:
    from .test_cashier import suite

__all__ = ['suite']
