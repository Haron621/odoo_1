# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_aba_payway import const
from odoo.addons.payment_aba_payway.tests.common import AbaPaywayCommon


@tagged("post_install", "-at_install")
class TestProcessingFlows(AbaPaywayCommon, PaymentHttpCommon):
    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_redirect_notification_triggers_processing(self):
        """Test that returning from the checkout fetches the payment data and processes them."""
        tx = self._create_transaction("direct")
        url = self._build_url(const.RETURN_ROUTE)
        with (
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction"
                "._send_api_request",
                return_value=self.check_transaction_response,
            ),
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction._record"
            ) as record_mock,
        ):
            self._make_http_get_request(url, params={"tran_id": tx.reference})
        self.assertEqual(record_mock.call_count, 1)

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_redirect_notification_skips_check_if_webhook_notification_was_received(self):
        """Test that returning from the checkout doesn't check the transaction if the webhook
        notification was already received, whether it was processed or not."""
        processed_tx = self._create_transaction("direct", reference="tx-processed", state="done")
        unprocessed_tx = self._create_transaction("direct", reference="tx-unprocessed")
        unprocessed_tx._record(self.webhook_payment_data)
        url = self._build_url(const.RETURN_ROUTE)
        for tx in (processed_tx, unprocessed_tx):
            with (
                self.subTest(reference=tx.reference),
                patch(
                    "odoo.addons.payment.models.payment_transaction.PaymentTransaction"
                    "._send_api_request"
                ) as request_mock,
            ):
                self._make_http_get_request(url, params={"tran_id": tx.reference})
                self.assertEqual(request_mock.call_count, 0)

    def _make_cancel_notification(self, tx, access_token=None):
        """Simulate the redirection to the cancel route with a successful closing request.

        :param payment.transaction tx: The transaction to cancel.
        :param str access_token: The access token to embed in the cancel URL; a valid one if None.
        :return: The mock of the request sent to ABA PayWay.
        :rtype: MagicMock
        """
        url = self._build_url(const.CANCEL_ROUTE)
        if access_token is None:
            access_token = payment_utils.generate_access_token(tx.reference, env=self.env)
        with patch(
            "odoo.addons.payment.models.payment_transaction.PaymentTransaction._send_api_request",
            return_value={"status": {"code": "00", "message": "Success!"}},
        ) as request_mock:
            self._make_http_get_request(
                url, params={"tran_id": tx.reference, "access_token": access_token}
            )
        return request_mock

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_cancel_notification_closes_transaction(self):
        """Test that closing the checkout closes the transaction on ABA PayWay."""
        tx = self._create_transaction("direct")
        request_mock = self._make_cancel_notification(tx)
        self.assertEqual(
            request_mock.call_args.args[1], "/api/payment-gateway/v1/payments/close-transaction"
        )

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_cancel_notification_cancels_transaction(self):
        """Test that closing the checkout cancels the transaction."""
        tx = self._create_transaction("direct")
        self._make_cancel_notification(tx)
        self.assertEqual(tx.state, "cancel")

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_cancel_notification_post_processes_transaction(self):
        """Test that the transaction is post-processed after being canceled, as the cancellation
        skips the processing cron."""
        tx = self._create_transaction("direct")
        self._make_cancel_notification(tx)
        self.assertTrue(tx.is_post_processed)

    @mute_logger(
        "odoo.addons.payment_aba_payway.controllers.main",
        "odoo.addons.payment_aba_payway.models.payment_transaction",
    )
    def test_cancel_notification_fetches_payment_data_if_transaction_cannot_be_closed(self):
        """Test that the payment data are fetched and processed if ABA PayWay refuses to close the
        transaction, e.g., because it was paid in the meantime."""
        self._disable_process_patcher()
        tx = self._create_transaction("direct")
        url = self._build_url(const.CANCEL_ROUTE)
        access_token = payment_utils.generate_access_token(tx.reference, env=self.env)
        with patch(
            "odoo.addons.payment.models.payment_transaction.PaymentTransaction._send_api_request",
            side_effect=[
                ValidationError("Transaction not found (5)"),
                self.check_transaction_response,
            ],
        ):
            self._make_http_get_request(
                url, params={"tran_id": tx.reference, "access_token": access_token}
            )
        self._run_processing()
        self.assertEqual(tx.state, "done")

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_cancel_notification_requires_valid_access_token(self):
        """Test that the transaction is not closed if the access token is invalid."""
        tx = self._create_transaction("direct")
        request_mock = self._make_cancel_notification(tx, access_token="dummy")
        self.assertEqual(request_mock.call_count, 0)

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_cancel_notification_skips_closing_if_webhook_notification_was_received(self):
        """Test that the transaction is not closed if the webhook notification was received."""
        tx = self._create_transaction("direct")
        tx._record(self.webhook_payment_data)
        request_mock = self._make_cancel_notification(tx)
        self.assertEqual(request_mock.call_count, 0)

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_webhook_notification_triggers_processing(self):
        """Test that receiving a valid webhook notification triggers the processing of the payment
        data."""
        self._create_transaction("direct")
        url = self._build_url(const.WEBHOOK_ROUTE)
        with (
            patch("odoo.addons.payment.utils.verify_signature"),
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction._record"
            ) as record_mock,
        ):
            self._make_json_request(url, data=self.webhook_payment_data)
        self.assertEqual(record_mock.call_count, 1)

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main")
    def test_webhook_notification_triggers_signature_check(self):
        """Test that receiving a webhook notification triggers a signature check."""
        self._create_transaction("direct")
        url = self._build_url(const.WEBHOOK_ROUTE)
        with patch("odoo.addons.payment.utils.verify_signature") as signature_check_mock:
            self.opener.headers["X-PayWay-HMAC-SHA512"] = self.webhook_payment_data_signature
            self._make_json_request(url, data=self.webhook_payment_data)
            self.opener.headers.pop("X-PayWay-HMAC-SHA512")

            self.assertEqual(
                signature_check_mock.call_args[0][0], self.webhook_payment_data_signature
            )

    @mute_logger(
        "odoo.addons.payment_aba_payway.controllers.main",
        "odoo.addons.payment.models.payment_transaction",
    )
    def test_webhook_notification_for_missing_transaction_is_acknowledged(self):
        """Test that a webhook notification for a missing transaction is acknowledged so that ABA
        PayWay doesn't retry sending it."""
        url = self._build_url(const.WEBHOOK_ROUTE)
        response = self._make_json_request(url, data=self.webhook_payment_data)
        self.assertEqual(response.status_code, 200)

    @mute_logger(
        "odoo.addons.payment_aba_payway.controllers.main",
        "odoo.addons.payment.models.payment_transaction",
    )
    def test_webhook_notification_skips_signature_verification_for_missing_transactions(self):
        """Test that the signature of a webhook notification for a missing transaction is not
        verified, as the API key of the provider is unknown."""
        url = self._build_url(const.WEBHOOK_ROUTE)
        with patch("odoo.addons.payment.utils.verify_signature") as signature_check_mock:
            self._make_json_request(url, data=self.webhook_payment_data)
        self.assertEqual(signature_check_mock.call_count, 0)

    def _make_tampered_webhook_notification(self):
        """Simulate a webhook notification whose signature doesn't match its data.

        :return: The response to the notification and the mock of the recording method.
        :rtype: tuple[Response, MagicMock]
        """
        self._create_transaction("direct")
        url = self._build_url(const.WEBHOOK_ROUTE)
        tampered_payment_data = dict(self.webhook_payment_data, original_amount=1)
        with patch(
            "odoo.addons.payment.models.payment_transaction.PaymentTransaction._record"
        ) as record_mock:
            self.opener.headers["X-PayWay-HMAC-SHA512"] = self.webhook_payment_data_signature
            response = self._make_json_request(url, data=tampered_payment_data)
            self.opener.headers.pop("X-PayWay-HMAC-SHA512")
        return response, record_mock

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main", "odoo.addons.payment.utils")
    def test_webhook_notification_with_invalid_signature_is_rejected(self):
        """Test that a webhook notification whose signature doesn't match its data is rejected."""
        response, _record_mock = self._make_tampered_webhook_notification()
        self.assertEqual(response.status_code, 403)

    @mute_logger("odoo.addons.payment_aba_payway.controllers.main", "odoo.addons.payment.utils")
    def test_webhook_notification_with_invalid_signature_is_not_recorded(self):
        """Test that the payment data of a webhook notification whose signature doesn't match its
        data are not recorded."""
        _response, record_mock = self._make_tampered_webhook_notification()
        self.assertEqual(record_mock.call_count, 0)
