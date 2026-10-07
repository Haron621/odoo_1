# Part of Odoo. See LICENSE file for full copyright and licensing details.

import unicodedata

from odoo.addons.payment import utils as payment_utils


def format_partner_name(partner_name):
    """Format the partner name to comply with the requirements of ABA PayWay.

    ABA PayWay rejects the purchase requests whose names contain special characters (e.g., `'`,
    `&`, `,`, `(`). Only the letters and marks of all scripts, spaces, hyphens and dots are kept.

    :param str partner_name: The name of the partner making the payment.
    :return: The sanitized first name and last name.
    :rtype: tuple[str, str]
    """
    sanitized_name = "".join(
        char for char in partner_name if unicodedata.category(char)[0] in "LM" or char in " -."
    )
    if not sanitized_name.strip():
        return "", ""
    return payment_utils.split_partner_name(sanitized_name)


def to_php_string(value):
    """Convert a value to a string following PHP's type juggling rules.

    ABA PayWay computes signatures from values converted to strings by PHP, which formats some
    values differently from Python (e.g., `100.0` -> `'100'`, `None` -> `''`).

    :param value: The value to convert.
    :return: The string representation of the value.
    :rtype: str
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
