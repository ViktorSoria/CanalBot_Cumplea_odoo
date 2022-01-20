# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from datetime import datetime, timedelta, timezone
import calendar
import logging
import pytz
from odoo.exceptions import ValidationError, UserError

_log = logging.getLogger("account_payment (%s) -------> " % __name__)


class AccountPaymentCustom(models.Model):
    _inherit = "account.payment"

    seller_original = fields.Many2one('res.users', string="Vendedor en Factura", compute='get_seller_from_invoice', store=True)
    date_payment_customer = fields.Datetime(string="Fecha de pago del cliente")
    date_payment_SAT = fields.Datetime(string="Fecha de Timbrado")
    date_change = fields.Boolean(string="Bool Date", compute='change_dates_payment')

    @api.depends('reconciled_invoice_ids')
    def get_seller_from_invoice(self):
        for rec in self:
            rec.seller_original = rec.reconciled_invoice_ids[0].invoice_user_id if rec.reconciled_invoice_ids else None

    def _default_start_date(self):
        date_now = datetime.now()
        date = datetime(self.date.year, self.date.month, self.date.day, date_now.hour, date_now.minute, date_now.second)
        return date

    @api.depends('date')
    def change_dates_payment(self):
        if self.date:
            date2datetime = self._default_start_date()
            self.date_payment_customer = date2datetime if not self.date_payment_customer else self.date_payment_customer
            self.date_payment_SAT = date2datetime if not self.date_payment_SAT else self.date_payment_SAT
        self.date_change = True

    def action_process_edi_web_services(self):
        date_SAT = self.date_payment_SAT
        date_PAY = self.date_payment_customer
        tz_str = self.env.user.tz or 'America/Mexico_City'
        tz = pytz.timezone(tz_str)

        date_SAT = date_SAT.astimezone(tz=tz)
        date_SAT = date_SAT.replace(tzinfo=None)

        date_PAY = date_PAY.astimezone(tz=tz)
        date_PAY = date_PAY.replace(tzinfo=None)

        objeto = self.with_context(date_SAT=date_SAT, date_PAY=date_PAY)
        return super(AccountPaymentCustom, objeto).action_process_edi_web_services()


class PermisoFacturascreditos(models.Model):
    _inherit = "account.move"

    permiso_saldo_aFavor = fields.Boolean(string="Aplicacion de saldos a favor en facturas", compute="creditInvoicePermission")
    pricelist_id = fields.Many2one('product.pricelist', string="Tarifa")

    def creditInvoicePermission(self):
        self.permiso_saldo_aFavor = self.env.user.has_group('sales_customs.group_edition_invoices_credits')


class SaleAdvanceInvoiceCustom(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self,order,name,amount, so_line):
        res = super(SaleAdvanceInvoiceCustom, self)._prepare_invoice_values(order,name,amount, so_line)
        res['pricelist_id'] = order.pricelist_id.id if order.pricelist_id else None
        return res

