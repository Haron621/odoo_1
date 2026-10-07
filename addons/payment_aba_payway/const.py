# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools import frozendict

# Route to which the customer is redirected after a successful payment
RETURN_ROUTE = "/payment/aba_payway/return"

# Route to which the customer is redirected after closing the checkout
CANCEL_ROUTE = "/payment/aba_payway/cancel"

# Route for ABA PayWay webhook notifications
WEBHOOK_ROUTE = "/payment/aba_payway/webhook"

# The currencies supported by ABA PayWay, in ISO 4217 format
SUPPORTED_CURRENCIES = ("KHR", "USD")

# The number of decimals to use for each supported currency, used for formatting and validating
# amounts
CURRENCY_DECIMALS = frozendict({"KHR": 0, "USD": 2})

# The codes of the default primary payment methods to activate
DEFAULT_PAYMENT_METHOD_CODES = {"aba_khqr", "alipay", "card", "wechat_pay"}

# Mapping of payment method codes to ABA PayWay payment options
PAYMENT_METHODS_MAPPING = frozendict({
    "aba_khqr": "abapay_khqr",
    "card": "cards",
    "wechat_pay": "wechat",
})

# Mapping of ABA PayWay payment types, sent in webhook notifications, to payment method codes.
# Unlike other mappings, it maps provider codes to Odoo codes, as several payment types can map to
# the same payment method.
PAYMENT_TYPES_MAPPING = frozendict({
    "ABA Pay": "aba_khqr",
    "KHQR": "aba_khqr",
    "Alipay": "alipay",
    "Wechat": "wechat_pay",
    "VISA": "visa",
    "MC": "mastercard",
    "JCB": "jcb",
    "CUP": "unionpay",
})

# Mapping of transaction states to ABA PayWay payment status codes.
# See https://developer.payway.com.kh/check-transaction-14530826e0.
PAYMENT_STATUS_MAPPING = frozendict({"done": ("0",), "cancel": ("7",), "error": ("3",)})

# The payment status code of payments not completed yet. Declined and expired payments keep this
# status, as the customer can retry the payment until the end of its lifetime.
UNPAID_PAYMENT_STATUS = "2"

# The keys of the purchase request to include in the signature, in the order in which they must be
# concatenated
PURCHASE_SIGNATURE_KEYS = (
    "req_time",
    "merchant_id",
    "tran_id",
    "amount",
    "firstname",
    "lastname",
    "email",
    "phone",
    "type",
    "payment_option",
    "return_url",
    "cancel_url",
    "continue_success_url",
    "currency",
    "lifetime",
    "skip_success_page",
)

# The keys of the check and close transaction requests to include in the signature, in the order in
# which they must be concatenated
TRANSACTION_REQUEST_SIGNATURE_KEYS = ("req_time", "merchant_id", "tran_id")
