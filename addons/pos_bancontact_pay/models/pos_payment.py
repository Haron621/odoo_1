import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import AccessDenied, UserError
from odoo.tools import float_compare

from odoo.addons.pos_bancontact_pay import const

_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    bancontact_id = fields.Char("Bancontact ID", readonly=True, copy=False, index='btree_not_null')
    bancontact_refunded_payment_id = fields.Many2one(
        'pos.payment',
        string="Refunded Bancontact Payment",
        readonly=True,
        copy=False,
        index='btree_not_null',
        help="The original Bancontact payment this refund reverses.",
    )
    bancontact_refund_ids = fields.One2many('pos.payment', 'bancontact_refunded_payment_id', string="Bancontact Refunds")
    bancontact_refund_id = fields.Char("Bancontact Refund ID", readonly=True, copy=False, index='btree_not_null')
    bancontact_refund_status = fields.Selection(
        selection=[
            ('pending', "Pending"),
            ('refunded', "Refunded"),
            ('failed', "Failed"),
        ],
        string="Bancontact Refund Status",
        readonly=True,
        copy=False,
    )

    @api.model
    def _get_additional_payment_fields(self):
        return super()._get_additional_payment_fields() + ["bancontact_id"]

    @api.model
    def get_bancontact_refundable_lines(self, order_id, config_id):
        """Return the Bancontact payments of an order that can still be refunded.

        The status of their pending refunds is refreshed first, so a failed refund gives its amount back.

        :param int order_id: id of the refunded order.
        :param int config_id: id of the POS config doing the refund.
        :return: one dict per refundable payment, with the amount left to refund and whether its
                 payment method is available in the POS config.
        :rtype: list[dict]
        """
        order = self.env['pos.order'].browse(order_id).exists()
        config = self.env['pos.config'].browse(config_id)
        payments = order.payment_ids.filtered(lambda payment: payment._bancontact_is_refundable_payment())
        payments.bancontact_refund_ids.filtered(lambda refund: refund.bancontact_refund_status == 'pending')._bancontact_refresh_refund_status()

        lines = []
        for payment in payments:
            amount_left = payment._bancontact_get_amount_left_to_refund()
            if float_compare(amount_left, 0, precision_rounding=payment.currency_id.rounding) <= 0:
                continue
            lines.append({
                'id': payment.id,
                'payment_method_id': payment.payment_method_id.id,
                'payment_method_name': payment.payment_method_id.name,
                'amount': payment.amount,
                'amount_left': amount_left,
                'in_config': payment.payment_method_id in config.payment_method_ids,
            })
        return lines

    def _bancontact_is_refundable_payment(self):
        """Return whether the payment is a successful Bancontact payment whose product allows refunds."""
        self.ensure_one()
        return bool(
            self.bancontact_id
            and self.payment_status == 'done'
            and float_compare(self.amount, 0, precision_rounding=self.currency_id.rounding) > 0
            and self.payment_method_id.payment_provider == 'bancontact_pay'
            and self.payment_method_id.bancontact_product_id.refund_enabled,
        )

    def _bancontact_get_amount_left_to_refund(self, exclude_uuid=None):
        """Return the amount of the payment that isn't refunded yet, nor being refunded.

        :param str exclude_uuid: uuid of a refund line to leave out, e.g. the one being sent.
        """
        self.ensure_one()
        refunds = self.bancontact_refund_ids.filtered(
            lambda refund: refund.bancontact_refund_status in ('pending', 'refunded') and refund.uuid != exclude_uuid,
        )
        return self.currency_id.round(self.amount - sum(abs(refund.amount) for refund in refunds))

    def _bancontact_refresh_refund_status(self):
        """Fetch the status of the refunds from Bancontact and store it."""
        for refund in self.filtered(lambda payment: payment.bancontact_refund_id and payment.bancontact_refunded_payment_id):
            try:
                refund.bancontact_refund_status = refund.payment_method_id._bancontact_fetch_refund_status(
                    refund.bancontact_refunded_payment_id.bancontact_id,
                    refund.bancontact_refund_id,
                )
            except (requests.RequestException, UserError, AccessDenied, KeyError, ValueError) as e:
                _logger.warning("%s refund status refresh failed: pos_payment_id=%s, reason=%s", const.LOG_PREFIX, refund.id, e)
