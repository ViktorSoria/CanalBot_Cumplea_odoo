

from odoo import fields, models, api
from odoo.exceptions import UserError
import xlrd
import tempfile
import csv
from io import StringIO
import base64
import logging

_logger = logging.getLogger("Report")


class Report_order(models.TransientModel):
    _name = "report.order"

    def _default_start_date(self):
        """ Find the earliest start_date of the latests sessions """
        # restrict to configs available to the user
        config_ids = self.env['pos.config'].search([]).ids
        # exclude configs has not been opened for 2 days
        self.env.cr.execute("""
            SELECT
            max(start_at) as start,
            config_id
            FROM pos_session
            WHERE config_id = ANY(%s)
            AND start_at > (NOW() - INTERVAL '5 DAYS')
            GROUP BY config_id
        """, (config_ids,))
        latest_start_dates = [res['start'] for res in self.env.cr.dictfetchall()]
        # earliest of the latest sessions
        return latest_start_dates and min(latest_start_dates) or fields.Datetime.now()

    start_date = fields.Datetime("Fehca de Inicio",required=True, default=_default_start_date)
    end_date = fields.Datetime("Fehca de Finalizacion",required=True, default=fields.Datetime.now)
    pos_config_ids = fields.Many2many('pos.config', 'pos_report_order', 'report','pos',string="Puntos de venta",
        default=lambda s: s.env['pos.config'].search([]))

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            self.end_date = self.start_date

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date and self.end_date < self.start_date:
            self.start_date = self.end_date

    def generate_report(self):
        data = {'date_start': self.start_date, 'date_stop': self.end_date, 'config_ids': self.pos_config_ids.ids}
        return self.env.ref('back_moto.reporte_consolidado').report_action([], data=data)


class ParticularReport(models.AbstractModel):
    _name = 'report.back_moto.reporte_consolidado'

    def _get_report_values(self, docids, data=None):
        _logger.warning(docids)
        _logger.warning(data)
        # return a custom rendering context
        return {
        }