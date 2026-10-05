# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from odoo.tools.urls import urljoin

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_aba_payway import const
from odoo.addons.payment_aba_payway import utils as aba_payway_utils

_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator="-", **kwargs):
        """Override of `payment` to ensure that ABA PayWay requirements for references are
        satisfied.

        ABA PayWay requirements for references are as follows:
        - References must be unique at provider level for a given merchant account.
          This is satisfied by singularizing the prefix with the current datetime. If two
          transactions are created simultaneously, `_compute_reference` ensures the uniqueness of
          references by suffixing a sequence number.
        - References must be at most 20 characters long.

        :param str provider_code: The code of the provider handling the transaction.
        :param str prefix: The custom prefix used to compute the full reference.
        :param str separator: The custom separator used to separate the prefix from the suffix.
        :return: The unique reference for the transaction.
        :rtype: str
        """
        if provider_code != "aba_payway":
            return super()._compute_reference(
                provider_code, prefix=prefix, separator=separator, **kwargs
            )

        prefix = payment_utils.singularize_reference_prefix(separator="", max_length=20)
        return super()._compute_reference(provider_code, prefix=prefix, separator="", **kwargs)

    def _get_specific_processing_values(self, processing_values):
        """Override of `payment` to return ABA PayWay-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction.
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        if self.provider_code != "aba_payway":
            return super()._get_specific_processing_values(processing_values)

        base_url = self.provider_id.get_base_url()
        first_name, last_name = aba_payway_utils.format_partner_name(self.partner_name or "")
        email = self.partner_email or ""
        phone = self.partner_phone or ""
        decimal_places = const.CURRENCY_DECIMALS.get(self.currency_id.name)
        cancel_params = {
            "tran_id": self.reference,
            "access_token": payment_utils.generate_access_token(self.reference, env=self.env),
        }
        checkout_values = {
            "req_time": self.create_date.strftime("%Y%m%d%H%M%S"),
            "merchant_id": self.provider_id.aba_payway_merchant_id,
            "tran_id": self.reference,
            "amount": str(float_round(self.amount, decimal_places, rounding_method="DOWN")),
            "firstname": first_name[:100],
            "lastname": last_name[:100],
            "email": email if len(email) <= 50 else "",
            "phone": phone if len(phone) <= 20 else "",
            "type": "purchase",
            "payment_option": const.PAYMENT_METHODS_MAPPING.get(
                self.payment_method_code, self.payment_method_code
            ),
            "return_url": urljoin(base_url, const.WEBHOOK_ROUTE),
            "cancel_url": urljoin(base_url, f"{const.CANCEL_ROUTE}?{url_encode(cancel_params)}"),
            "continue_success_url": urljoin(
                base_url, f"{const.RETURN_ROUTE}?{url_encode({'tran_id': self.reference})}"
            ),
            "currency": self.currency_id.name,
            "lifetime": 3,  # The minimum lifetime of the payment, in minutes
            "skip_success_page": 1,
            "payment_gate": 0,  # Use the checkout service rather than the QR payment API
            "form_url": urljoin(
                self.provider_id._aba_payway_get_api_url(),
                "/api/payment-gateway/v1/payments/purchase",
            ),
        }
        checkout_values["hash"] = self.provider_id._aba_payway_calculate_signature(checkout_values)
        return checkout_values

    def _aba_payway_fetch_payment_data(self):
        """Fetch the payment data of the transaction from ABA PayWay and record them.

        ABA PayWay sends webhook notifications only to whitelisted domains, and their delivery is
        not guaranteed. Checking the transaction when the customer is redirected back to Odoo
        ensures that the payment is processed even if the notification is late or never received.

        Note: self.ensure_one()

        :return: None
        """
        try:
            response_content = self._aba_payway_send_transaction_request(
                "/api/payment-gateway/v1/payments/check-transaction-2"
            )
        except ValidationError as error:
            _logger.warning(
                "Unable to fetch the payment data of transaction %s: %s", self.reference, error
            )
            return

        payment_data = response_content.get("data", {})
        self._record({
            "tran_id": self.reference,
            "status": payment_data.get("payment_status_code"),
            "apv": payment_data.get("apv"),
            "original_amount": payment_data.get("original_amount"),
            # The original currency is not returned, but it is part of the signed purchase request
            "original_currency": self.currency_id.name,
        })

    def _aba_payway_close_transaction(self):
        """Close the transaction on ABA PayWay and cancel it.

        ABA PayWay never reports unpaid transactions as failed: declined and expired payments keep
        the pending status, and no webhook notification is sent. Closing the transaction when the
        customer closes the checkout ensures that it can no longer be paid, and thus that it can
        safely be canceled. As ABA PayWay refuses to close paid transactions, the payment data are
        fetched instead if the transaction cannot be closed.

        Note: self.ensure_one()

        :return: None
        """
        try:
            self._aba_payway_send_transaction_request(
                "/api/payment-gateway/v1/payments/close-transaction"
            )
        except ValidationError:
            self._aba_payway_fetch_payment_data()
        else:
            self.with_context(
                payment_safe_write=True  # Closed on ABA PayWay; no concurrent write is possible
            )._set_canceled()
            # Post-process immediately, as the state change skipped the processing cron
            self._try_post_process()

    def _aba_payway_send_transaction_request(self, endpoint):
        """Send a signed request about the transaction to ABA PayWay.

        Note: self.ensure_one()

        :param str endpoint: The endpoint of the API to reach with the request.
        :return: The content of the response.
        :rtype: dict
        :raise ValidationError: If the request fails or ABA PayWay returns an error.
        """
        self.ensure_one()

        payload = {
            "req_time": fields.Datetime.now().strftime("%Y%m%d%H%M%S"),
            "merchant_id": self.provider_id.aba_payway_merchant_id,
            "tran_id": self.reference,
        }
        payload["hash"] = self.provider_id._aba_payway_calculate_signature(
            payload, keys=const.TRANSACTION_REQUEST_SIGNATURE_KEYS
        )
        response_content = self._send_api_request("POST", endpoint, json=payload)
        status = response_content.get("status", {})
        if status.get("code") != "00":  # ABA PayWay returns some errors with a 200 status code
            raise ValidationError(
                self.env._(
                    "The payment provider rejected the request.\n%s",
                    f"{status.get('message')} ({status.get('code')})",
                )
            )
        return response_content

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """Override of `payment` to extract the reference from the payment data."""
        if provider_code != "aba_payway":
            return super()._extract_reference(provider_code, payment_data)

        return payment_data.get("tran_id")

    def _extract_amount_data(self, payment_data):
        """Override of `payment` to extract the amount and currency from the payment data."""
        if self.provider_code != "aba_payway":
            return super()._extract_amount_data(payment_data)

        # The original amount and currency are those of the payment request, before any discount
        # or currency conversion applied by ABA PayWay
        currency_code = payment_data.get("original_currency")
        return {
            "amount": float(payment_data.get("original_amount", 0)),
            "currency_code": currency_code,
            "precision_digits": const.CURRENCY_DECIMALS.get(currency_code),
        }

    def _apply_updates(self, payment_data):
        """Override of `payment` to update the transaction based on the payment data."""
        if self.provider_code != "aba_payway":
            super()._apply_updates(payment_data)
            return

        # Update the provider reference
        if provider_reference := payment_data.get("apv"):
            self.provider_reference = provider_reference

        # Update the payment method
        payment_type = payment_data.get("payment_type")
        payment_method = self.provider_id._get_pm_from_code(
            const.PAYMENT_TYPES_MAPPING.get(payment_type)
        )
        self.payment_method_id = payment_method or self.payment_method_id

        # Update the payment state
        payment_status = payment_data.get("status")
        if payment_status is None:  # Don't use a falsy check; the success status can be 0
            self._set_error(self.env._("Received data with missing status."))
            return

        payment_status = str(payment_status)
        if payment_status == const.UNPAID_PAYMENT_STATUS:
            # The payment was not completed yet; the transaction is left in draft until the customer
            # completes the payment
            _logger.info("Received data for unpaid transaction %s.", self.reference)
        elif payment_status in const.PAYMENT_STATUS_MAPPING["done"]:
            self._set_done()
        elif payment_status in const.PAYMENT_STATUS_MAPPING["cancel"]:
            self._set_canceled()
        elif payment_status in const.PAYMENT_STATUS_MAPPING["error"]:
            self._set_error(self.env._("The payment was declined."))
        else:
            _logger.warning(
                "Received data for transaction %s with invalid payment status: %s.",
                self.reference,
                payment_status,
            )
            self._set_error(
                self.env._("Received data with invalid payment status: %s.", payment_status)
            )
