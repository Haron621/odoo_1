import logging
from json import JSONDecodeError

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from odoo.addons.pos_bancontact_pay import const
from odoo.addons.pos_bancontact_pay.errors.http import HTTP_ERRORS, REFUND_ERRORS

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    # ----- Fields ----- #
    def _get_external_qr_provider_selection(self):
        return super()._get_external_qr_provider_selection() + [("bancontact_pay", "Bancontact Pay")]

    bancontact_product_id = fields.Many2one("pos.bancontact.product", string="Bancontact Product", ondelete="restrict", copy=False, check_company=True)
    bancontact_usage = fields.Selection(related="bancontact_product_id.usage")
    bancontact_sticker_id = fields.Many2one(
        "pos.bancontact.sticker",
        string="Bancontact Sticker",
        ondelete="restrict",
        copy=False,
        domain="[('product_id', '=', bancontact_product_id), ('payment_method_id', 'in', [False, id])]",
    )

    _bancontact_sticker_unique = models.Constraint(
        "unique (bancontact_sticker_id)",
        "This Bancontact sticker is already linked to another payment method.",
    )

    # ----- Model ----- #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("bancontact_sticker_id"):
                self._bancontact_reset_sticker_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if "payment_provider" in vals and vals["payment_provider"] != "bancontact_pay":
            vals["bancontact_product_id"] = False
        if "bancontact_product_id" in vals:
            self._bancontact_reset_sticker_vals(vals)
        return super().write(vals)

    @api.model
    def _bancontact_reset_sticker_vals(self, vals):
        """Drop the sticker when the selected Bancontact product isn't used with stickers."""
        product = self.env["pos.bancontact.product"].browse(vals.get("bancontact_product_id"))
        if product.usage != "sticker":
            vals["bancontact_sticker_id"] = False

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ["bancontact_usage"]

    @api.constrains("payment_provider", "journal_id", "company_id")
    def _check_bancontact_currency(self):
        """Ensure Bancontact Pay methods are linked to a supported journal currency."""
        for record in self:
            if record.payment_provider != "bancontact_pay":
                continue

            currency = record.journal_id.currency_id or record.company_id.currency_id
            if currency.name not in const.SUPPORTED_CURRENCIES:
                raise ValidationError(
                    _(
                        "Bancontact Pay only supports these currencies: %(currencies)s.\n"
                        "The linked journal uses a different currency.",
                        currencies=", ".join(const.SUPPORTED_CURRENCIES),
                    ),
                )

    @api.constrains("payment_provider", "bancontact_product_id", "config_ids")
    def _check_bancontact_sticker_one_pos_config(self):
        """Restrict Bancontact sticker methods to a single PoS configuration."""
        for record in self:
            if (
                record.payment_provider == "bancontact_pay"
                and record.bancontact_usage == "sticker"
                and len(record.config_ids) > 1
            ):
                raise ValidationError(_("One Bancontact Pay sticker payment method can only be linked to one POS configuration."))

    @api.constrains("payment_provider", "bancontact_product_id", "bancontact_sticker_id")
    def _check_bancontact_product(self):
        """Ensure Bancontact Pay methods are linked to a product, and their sticker belongs to that product."""
        for record in self:
            if record.payment_provider != "bancontact_pay" or not record.bancontact_product_id:
                continue

            if record.bancontact_usage == "sticker" and not record.bancontact_sticker_id:
                raise ValidationError(_("A Bancontact sticker must be set when using Bancontact Pay with sticker usage."))
            if record.bancontact_sticker_id and record.bancontact_sticker_id.product_id != record.bancontact_product_id:
                raise ValidationError(_("The Bancontact sticker must belong to the selected Bancontact product."))

    @api.onchange("bancontact_product_id")
    def _onchange_bancontact_product_id(self):
        if self.bancontact_usage == "sticker" and self.bancontact_sticker_id.product_id != self.bancontact_product_id:
            self.bancontact_sticker_id = False

    def download_bancontact_sticker(self):
        self.ensure_one()
        return self.bancontact_sticker_id.download_sticker()

    # ----- Bancontact Integration ----- #
    def create_bancontact_payment(self, data):
        self.ensure_one()
        if self.payment_provider != "bancontact_pay":
            raise ValidationError(_("Bancontact payments can only be created for payment methods using Bancontact Pay as provider."))
        self._check_bancontact_product_set()

        headers = {
            "Authorization": f"Bearer {self.bancontact_product_id.sudo().api_key}",
            "Content-Type": "application/json",
        }
        url, payload = self._prepare_bancontact_payment_request(data)
        response = None
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            self._assert_bancontact_http_success(response)
            bancontact_data = response.json()
        except Exception as e:
            reason = response.text if response is not None else str(e)
            _logger.warning("%s payment creation failed: ppid=%s, reason=%s, data=%s", const.LOG_PREFIX, self.bancontact_product_id.ppid, reason, data)
            raise

        bancontact_id = bancontact_data["paymentId"]
        bancontact_qr = bancontact_data.get("_links", {}).get("qrcode", {}).get("href", "")
        if bancontact_qr:
            bancontact_qr += "&f=SVG"

        _logger.info("%s payment creation succeeded: ppid=%s, bancontact_id=%s", const.LOG_PREFIX, self.bancontact_product_id.ppid, bancontact_id)
        return {
            "bancontact_id": bancontact_id,
            "qr_code": bancontact_qr,
        }

    def cancel_bancontact_payment(self, bancontact_id):
        self.ensure_one()
        if self.payment_provider != "bancontact_pay":
            raise ValidationError(_("Bancontact payments can only be cancelled for payment methods using Bancontact Pay as provider."))
        self._check_bancontact_product_set()

        url = f"{self._get_bancontact_api_url('merchant')}/v3/payments/{bancontact_id}"
        headers = {
            "Authorization": f"Bearer {self.bancontact_product_id.sudo().api_key}",
            "Content-Type": "application/json",
        }

        response = None
        try:
            response = requests.delete(url, headers=headers, timeout=5)
            self._assert_bancontact_http_success(response,
                {422: (_("Unable to cancel payment. The payment may not be in a cancellable state."), ValidationError)},
            )
        except Exception as e:
            reason = response.text if response is not None else str(e)
            _logger.warning("%s payment cancellation failed: ppid=%s, bancontact_id=%s, reason=%s", const.LOG_PREFIX, self.bancontact_product_id.ppid, bancontact_id, reason)
            raise

    def create_bancontact_refund(self, data):
        """Ask Bancontact to refund (part of) a Bancontact payment.

        :param dict data: the refund line, with ``refunded_payment_id`` (id of the original
                          ``pos.payment``), ``amount``, ``uuid``, ``description`` and
                          ``idempotency_key`` (the uuid by default; a new key is needed to retry a
                          failed refund, as Bancontact returns the same refund for the same key).
        :return: the Bancontact refund ID and status.
        :rtype: dict
        """
        self.ensure_one()
        refunded_payment = self.env["pos.payment"].browse(data.get("refunded_payment_id")).exists()
        self._check_bancontact_refund(refunded_payment)

        amount = refunded_payment.currency_id.round(abs(data.get("amount", 0.0)))
        if float_compare(amount, 0, precision_rounding=refunded_payment.currency_id.rounding) <= 0:
            raise ValidationError(_("The refund amount must be positive."))
        refunded_payment.bancontact_refund_ids.filtered(lambda refund: refund.bancontact_refund_status == "pending")._bancontact_refresh_refund_status()
        amount_left = refunded_payment._bancontact_get_amount_left_to_refund(exclude_uuid=data.get("uuid"))
        if float_compare(amount, amount_left, precision_rounding=refunded_payment.currency_id.rounding) > 0:
            raise ValidationError(_(
                "Only %(amount_left)s can still be refunded on this Bancontact payment.",
                amount_left=refunded_payment.currency_id.format(amount_left),
            ))

        product = self.bancontact_product_id
        bancontact_id = refunded_payment.bancontact_id
        payload = {
            "amount": round(amount * 100),
            "currency": refunded_payment.currency_id.name,
        }
        if data.get("description"):
            payload["description"] = data["description"]
        response = None
        try:
            response = product._send_bancontact_signed_request("POST", f"/v3/payments/{bancontact_id}/refunds", payload, idempotency_key=data.get("idempotency_key") or data.get("uuid"))
            self._assert_bancontact_http_success(response, code_errors=REFUND_ERRORS)
            bancontact_data = response.json()
        except Exception as e:
            reason = response.text if response is not None else str(e)
            _logger.warning("%s refund creation failed: ppid=%s, bancontact_id=%s, reason=%s, data=%s", const.LOG_PREFIX, product.ppid, bancontact_id, reason, data)
            raise

        refund_id = bancontact_data["refundId"]
        _logger.info("%s refund creation succeeded: ppid=%s, bancontact_id=%s, refund_id=%s", const.LOG_PREFIX, product.ppid, bancontact_id, refund_id)
        return {
            "bancontact_refund_id": refund_id,
            "bancontact_refund_status": bancontact_data.get("status", "PENDING").lower(),
        }

    def get_bancontact_refund_status(self, data):
        """Return the status of a Bancontact refund, and store it on its refund line if it exists.

        :param dict data: the refund line, with ``refunded_payment_id`` (id of the original
                          ``pos.payment``) and ``bancontact_refund_id``.
        :return: ``pending``, ``refunded`` or ``failed``.
        :rtype: str
        """
        self.ensure_one()
        refunded_payment = self.env["pos.payment"].browse(data.get("refunded_payment_id")).exists()
        if refunded_payment.payment_method_id != self or not refunded_payment.bancontact_id:
            raise ValidationError(_("This refund doesn't belong to a Bancontact payment of the payment method '%(method_name)s'.", method_name=self.name))

        refund_id = data.get("bancontact_refund_id")
        status = self._bancontact_fetch_refund_status(refunded_payment.bancontact_id, refund_id)
        refunded_payment.bancontact_refund_ids.filtered(lambda refund: refund.bancontact_refund_id == refund_id).bancontact_refund_status = status
        return status

    def _bancontact_fetch_refund_status(self, bancontact_id, refund_id):
        """Fetch the status of a refund from Bancontact.

        :param str bancontact_id: ID of the refunded Bancontact payment.
        :param str refund_id: ID of the Bancontact refund.
        :return: ``pending``, ``refunded`` or ``failed``.
        :rtype: str
        """
        self.ensure_one()
        self._check_bancontact_product_set()
        product = self.bancontact_product_id
        response = None
        try:
            response = product._send_bancontact_signed_request("GET", f"/v3/payments/{bancontact_id}/refunds/{refund_id}")
            self._assert_bancontact_http_success(response)
            status = response.json()["status"].lower()
        except Exception as e:
            reason = response.text if response is not None else str(e)
            _logger.warning("%s refund status fetch failed: ppid=%s, bancontact_id=%s, refund_id=%s, reason=%s", const.LOG_PREFIX, product.ppid, bancontact_id, refund_id, reason)
            raise
        return status

    # ----- Helpers ----- #
    def _check_bancontact_refund(self, refunded_payment):
        """Ensure the payment method can refund the given Bancontact payment."""
        if self.payment_provider != "bancontact_pay":
            raise ValidationError(_("Bancontact refunds can only be created for payment methods using Bancontact Pay as provider."))
        self._check_bancontact_product_set()
        if not self.bancontact_product_id.refund_enabled:
            raise ValidationError(_("Refunds are not enabled on the Bancontact product '%(product_name)s'.", product_name=self.bancontact_product_id.name))
        if refunded_payment.payment_method_id != self or not refunded_payment._bancontact_is_refundable_payment():
            raise ValidationError(_("Only a successful Bancontact payment made with the payment method '%(method_name)s' can be refunded with it.", method_name=self.name))

    def _check_bancontact_product_set(self):
        if not self.bancontact_product_id:
            raise ValidationError(_("No Bancontact product is configured on the payment method '%(method_name)s'.", method_name=self.name))

    def _get_callback_url(self, data):
        """Build the callback URL used by Bancontact Pay to notify payment status."""
        config_id = data.get("configId")
        return f"{self.get_base_url()}/bancontact_pay/webhook?config_id={config_id}&payment_method_id={self.id}"

    def _prepare_bancontact_payment_request(self, data):
        """Prepare the endpoint and JSON payload for a Bancontact payment creation call."""
        if self.bancontact_usage == "sticker":
            return self._prepare_sticker_payment_request(data)
        return self._prepare_display_payment_request(data)

    def _prepare_display_payment_request(self, data):
        """Prepare the request data for a dynamic on-screen QR payment."""
        callback_url = self._get_callback_url(data)
        return [
            f"{self._get_bancontact_api_url('merchant')}/v3/payments",
            {
                "reference": data.get("uuid", "").replace("-", "")[:35],
                "amount": round(data.get("amount", 0.0) * 100),
                "currency": data.get("currency", "EUR"),
                "description": data.get("description", "")[:140],
                "identifyCallbackUrl": callback_url,
                "callbackUrl": callback_url,
            },
        ]

    def _prepare_sticker_payment_request(self, data):
        """Prepare the request data for a static sticker-based QR payment."""
        callback_url = self._get_callback_url(data)
        return [
            f"{self._get_bancontact_api_url('merchant')}/v3/payments/pos",
            {
                "reference": data.get("uuid", "").replace("-", "")[:35],
                "amount": round(data.get("amount", 0.0) * 100),
                "currency": data.get("currency", "EUR"),
                "description": data.get("description", "")[:140],
                "posId": self.bancontact_sticker_id.identifier,
                "shopId": f'pos{data.get("configId", "")}'[:36],
                "shopName": data.get("shopName", "")[:36],
                "identifyCallbackUrl": callback_url,
                "callbackUrl": callback_url,
            },
        ]

    def _get_bancontact_api_url(self, target):
        """Return the Bancontact endpoint URL for the current environment."""
        return self.bancontact_product_id._get_bancontact_api_url(target)

    def _assert_bancontact_http_success(self, response, extra_errors=None, code_errors=None):
        """Raise an error when the Bancontact request failed.

        :param dict extra_errors: (message, exception class) per HTTP status, on top of the default ones.
        :param dict code_errors: message per Bancontact error code, taking precedence over the
                                 message of the HTTP status.
        """
        errors = {**HTTP_ERRORS, **(extra_errors or {})}
        if response.status_code in errors:
            error_message, exception_class = errors[response.status_code]
            try:
                error_data = response.json()
            except JSONDecodeError:
                error_data = {}
            code = error_data.get("code", "")
            if code in (code_errors or {}):
                error_message, exception_class = code_errors[code], ValidationError

            exception_msg = f"{error_message} (ERR: {response.status_code}"
            if code:
                exception_msg += f" - {code}"
            exception_msg += ")"
            raise exception_class(exception_msg)

        response.raise_for_status()
