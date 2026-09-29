# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    l10n_jp_display_currency_code = fields.Boolean(related='company_id.l10n_jp_display_currency_code', readonly=False)
    l10n_jp_is_jp_layout = fields.Boolean(compute='_compute_l10n_jp_is_jp_layout')

    @api.depends('report_layout_id')
    def _compute_l10n_jp_is_jp_layout(self):
        jp_layout = self.env.ref('l10n_jp.report_layout_jp_standard', raise_if_not_found=False)
        for wizard in self:
            wizard.l10n_jp_is_jp_layout = bool(jp_layout) and wizard.report_layout_id == jp_layout

    @api.model
    def _extract_company_layout_vals(self, vals):
        # The account configurator writes the company as superuser, and only
        # the fields it is told about; the others would reach the company with
        # the rights of an accountant, who cannot write it.
        jp_vals = {'l10n_jp_display_currency_code': vals.pop('l10n_jp_display_currency_code')} \
            if 'l10n_jp_display_currency_code' in vals else {}
        return super()._extract_company_layout_vals(vals) | jp_vals
