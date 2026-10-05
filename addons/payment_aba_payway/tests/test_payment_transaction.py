# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from freezegun import freeze_time
from werkzeug.urls import url_encode

from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.urls import urljoin

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_aba_payway import const
from odoo.addons.payment_aba_payway.tests.common import AbaPaywayCommon


@tagged("post_install", "-at_install")
class TestPaymentTransaction(AbaPaywayCommon):
    @freeze_time("2011-11-02 12:00:21")  # Freeze time for consistent singularization behavior
    def test_reference_is_singularized(self):
        """Test the singularization of reference prefixes."""
        reference = self.env["payment.transaction"]._compute_reference(self.provider.code)
        self.assertEqual(reference, "tx20111102120021")

    def test_reference_length_is_at_most_20_chars(self):
        """The computed reference must be at most 20 characters long."""
        reference = self.env["payment.transaction"]._compute_reference(self.provider.code)
        self.assertLessEqual(len(reference), 20)

    def test_no_item_missing_from_processing_values(self):
        """Test that the processing values are conform to the transaction fields."""
        tx = self._create_transaction("direct")
        base_url = self.provider.get_base_url()
        cancel_params = {
            "tran_id": tx.reference,
            "access_token": payment_utils.generate_access_token(tx.reference, env=self.env),
        }
        with patch(
            "odoo.addons.payment_aba_payway.models.payment_provider.PaymentProvider"
            "._aba_payway_calculate_signature",
            return_value="dummy_signature",
        ):
            processing_values = tx._get_specific_processing_values({})
        self.maxDiff = None
        self.assertDictEqual(
            processing_values,
            {
                "req_time": tx.create_date.strftime("%Y%m%d%H%M%S"),
                "merchant_id": self.provider.aba_payway_merchant_id,
                "tran_id": tx.reference,
                "amount": "2213",
                "firstname": "Norbert",
                "lastname": "Buyer",
                "email": tx.partner_email,
                "phone": tx.partner_phone,
                "type": "purchase",
                "payment_option": const.PAYMENT_METHODS_MAPPING["card"],
                "return_url": urljoin(base_url, const.WEBHOOK_ROUTE),
                "cancel_url": urljoin(
                    base_url, f"{const.CANCEL_ROUTE}?{url_encode(cancel_params)}"
                ),
                "continue_success_url": urljoin(
                    base_url, f"{const.RETURN_ROUTE}?{url_encode({'tran_id': tx.reference})}"
                ),
                "currency": tx.currency_id.name,
                "lifetime": 3,
                "skip_success_page": 1,
                "payment_gate": 0,
                "form_url": urljoin(
                    self.provider._aba_payway_get_api_url(),
                    "/api/payment-gateway/v1/payments/purchase",
                ),
                "hash": "dummy_signature",
            },
        )

    def test_processing_values_contain_rounded_amount_khr(self):
        """Ensure that for KHR currency, the processing values contain the amount rounded down to
        the nearest unit."""
        tx = self._create_transaction("direct", amount=2213.75)
        processing_values = tx._get_specific_processing_values({})
        self.assertEqual(processing_values["amount"], "2213")

    def test_processing_values_omit_missing_partner_details(self):
        """Test that missing partner details are sent as empty strings."""
        partner = self.env["res.partner"].create({"name": "Norbert Buyer"})
        tx = self._create_transaction("direct", partner_id=partner.id)
        processing_values = tx._get_specific_processing_values({})
        for key in ("email", "phone"):
            with self.subTest(key=key):
                self.assertEqual(processing_values[key], "")

    def test_processing_values_truncate_partner_names(self):
        """Test that the partner names are truncated to the maximum length allowed by ABA PayWay."""
        partner = self.env["res.partner"].create({"name": f"{'a' * 120} {'b' * 120}"})
        tx = self._create_transaction("direct", partner_id=partner.id)
        processing_values = tx._get_specific_processing_values({})
        for key, expected_name in (("firstname", "a" * 100), ("lastname", "b" * 100)):
            with self.subTest(key=key):
                self.assertEqual(processing_values[key], expected_name)

    def test_processing_values_contain_sanitized_partner_names(self):
        """Test that the characters rejected by ABA PayWay are removed from the partner names."""
        for partner_name, expected_names in (
            ("Norbert O'Brien", ("Norbert", "OBrien")),
            ("Jean-Luc (Admin), Jr.", ("Jean-Luc Admin", "Jr.")),
            ("សុខ ដារ៉ា", ("សុខ", "ដារ៉ា")),
            ("'&,", ("", "")),
        ):
            with self.subTest(partner_name=partner_name):
                partner = self.env["res.partner"].create({"name": partner_name})
                tx = self._create_transaction(
                    "direct", reference=f"tx-{partner.id}", partner_id=partner.id
                )
                processing_values = tx._get_specific_processing_values({})
                self.assertEqual(
                    (processing_values["firstname"], processing_values["lastname"]), expected_names
                )

    def _fetch_payment_data(self, tx):
        """Fetch the payment data of the transaction without recording them.

        :param payment.transaction tx: The transaction whose payment data to fetch.
        :return: The payload of the request sent to the check transaction API.
        :rtype: dict
        """
        with (
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction"
                "._send_api_request",
                return_value=self.check_transaction_response,
            ) as request_mock,
            patch("odoo.addons.payment.models.payment_transaction.PaymentTransaction._record"),
        ):
            tx._aba_payway_fetch_payment_data()
        return request_mock.call_args.kwargs["json"]

    def test_fetch_payment_data_requests_transaction(self):
        """Test that the check transaction API is requested for the transaction."""
        tx = self._create_transaction("direct")
        payload = self._fetch_payment_data(tx)
        self.assertEqual(payload["tran_id"], tx.reference)

    def test_fetch_payment_data_sends_signed_request(self):
        """Test that the request sent to the check transaction API is signed."""
        tx = self._create_transaction("direct")
        payload = self._fetch_payment_data(tx)
        self.assertEqual(
            payload["hash"],
            self.provider._aba_payway_calculate_signature(
                payload, keys=const.TRANSACTION_REQUEST_SIGNATURE_KEYS
            ),
        )

    def test_fetch_payment_data_records_formatted_payment_data(self):
        """Test that the payment data fetched from the check transaction API are recorded in the
        format of the payment data of webhook notifications."""
        tx = self._create_transaction("direct")
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
            tx._aba_payway_fetch_payment_data()
        record_mock.assert_called_once_with({
            "tran_id": tx.reference,
            "status": 0,
            "apv": "544415",
            "original_amount": self.amount,
            "original_currency": self.currency.name,
        })

    @mute_logger("odoo.addons.payment_aba_payway.models.payment_transaction")
    def test_fetch_payment_data_ignores_error_response(self):
        """Test that no payment data are recorded when the check transaction API returns an error
        with a 200 status code."""
        tx = self._create_transaction("direct")
        with (
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction"
                "._send_api_request",
                return_value={"status": {"code": "6", "message": "tran_id not found"}},
            ),
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction._record"
            ) as record_mock,
        ):
            tx._aba_payway_fetch_payment_data()
        self.assertEqual(record_mock.call_count, 0)

    def test_extract_reference_finds_reference(self):
        """Test that the transaction reference is found in the payment data."""
        tx = self._create_transaction("direct")
        reference = self.env["payment.transaction"]._extract_reference(
            "aba_payway", self.webhook_payment_data
        )
        self.assertEqual(tx.reference, reference)

    def test_extract_amount_data_returns_amount_and_currency(self):
        """Test that the amount and currency are returned from the payment data."""
        tx = self._create_transaction("direct")
        amount_data = tx._extract_amount_data(self.webhook_payment_data)
        self.assertDictEqual(
            amount_data,
            {"amount": tx.amount, "currency_code": tx.currency_id.name, "precision_digits": 0},
        )

    def test_apply_updates_sets_provider_reference(self):
        """Test that the provider reference is updated from the payment data."""
        tx = self._create_transaction("direct")
        tx.with_context(payment_safe_write=True)._apply_updates(self.webhook_payment_data)
        self.assertEqual(tx.provider_reference, self.webhook_payment_data["apv"])

    def test_apply_updates_sets_payment_method(self):
        """Test that the payment method is updated from the payment data."""
        for payment_type, payment_method_code in const.PAYMENT_TYPES_MAPPING.items():
            with self.subTest(payment_type=payment_type):
                tx = self._create_transaction("direct", reference=f"tx-{payment_type}")
                payment_data = dict(self.webhook_payment_data, payment_type=payment_type)
                tx.with_context(payment_safe_write=True)._apply_updates(payment_data)
                self.assertEqual(tx.payment_method_code, payment_method_code)

    def test_apply_updates_keeps_payment_method_for_unknown_payment_type(self):
        """Test that the payment method is kept when the payment type is unknown."""
        tx = self._create_transaction("direct")
        payment_data = dict(self.webhook_payment_data, payment_type="Unknown")
        tx.with_context(payment_safe_write=True)._apply_updates(payment_data)
        self.assertEqual(tx.payment_method_id, self.payment_method_card)

    def test_apply_updates_confirms_transaction(self):
        """Test that the transaction state is set to 'done' when the payment data indicate a
        successful payment."""
        tx = self._create_transaction("direct")
        tx.with_context(payment_safe_write=True)._apply_updates(self.webhook_payment_data)
        self.assertEqual(tx.state, "done")

    def test_apply_updates_sets_transaction_state_from_payment_status(self):
        """Test that the transaction state is updated according to the payment status."""
        for status, expected_state in (("2", "draft"), ("7", "cancel"), ("3", "error")):
            with self.subTest(status=status):
                tx = self._create_transaction("direct", reference=f"tx-status-{status}")
                payment_data = dict(self.webhook_payment_data, status=status)
                tx.with_context(payment_safe_write=True)._apply_updates(payment_data)
                self.assertEqual(tx.state, expected_state)

    @mute_logger("odoo.addons.payment_aba_payway.models.payment_transaction")
    def test_apply_updates_sets_transaction_in_error(self):
        """Test that the transaction state is set to 'error' when the payment data indicate an
        unknown payment status."""
        tx = self._create_transaction("direct")
        payment_data = dict(self.webhook_payment_data, status="99")
        tx.with_context(payment_safe_write=True)._apply_updates(payment_data)
        self.assertEqual(tx.state, "error")

    def test_apply_updates_sets_transaction_in_error_for_missing_status(self):
        """Test that the transaction state is set to 'error' when the payment data have no payment
        status."""
        tx = self._create_transaction("direct")
        payment_data = dict(self.webhook_payment_data)
        del payment_data["status"]
        tx.with_context(payment_safe_write=True)._apply_updates(payment_data)
        self.assertEqual(tx.state, "error")
