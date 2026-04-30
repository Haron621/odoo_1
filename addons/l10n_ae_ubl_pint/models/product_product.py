from odoo import fields, models

# AE-GoodsType code list, exported as cbc:NatureCode ("Type of goods or services").
# https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/codelist/GoodsType/
L10N_AE_GOODS_SERVICE_TYPE_SELECTION = [
    ('DL8.48.8.2', 'Electronic Devices'),
    ('DL8.48.8.1', 'Gold and Diamonds'),
    ('DL8.48.3.1', 'Crude or refined oil'),
    ('DL8.48.3.2', 'Unprocessed or processed natural gas'),
    ('DL8.48.3.3', 'Pure hydrocarbons'),
]


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'l10n.ae.pint.check.mixin']

    # Item type (BTAE-13, cbc:CommodityCode) is one of G / S / B - this flag selects 'B',
    # the rest is derived from product.type in the exporter.
    # https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/semantic-model/btae-13/ - https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/codelist/ItemType/
    l10n_ae_is_good_and_service = fields.Boolean(
        string='Is Good and Service',
        copy=False,
    )
    l10n_ae_goods_service_type = fields.Selection(
        string='Goods and Service Type',
        selection=L10N_AE_GOODS_SERVICE_TYPE_SELECTION,
        copy=False,
    )
    # Item classification identifier (IBT-158, an HS code) and Service accounting code
    # (BTAE-17, a SAC) are different code systems in different UBL nodes, so they get a field
    # each: an item of type 'Both' (ibr-186-ae) must carry one of each, and reusing a single
    # value would file an HS code as a SAC - valid against the schematron, wrong to the FTA.
    # https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/semantic-model/ibt-158/ - https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/semantic-model/btae-17/
    l10n_ae_classification_code = fields.Char(
        string='HS Code',
        copy=False,
    )
    l10n_ae_service_accounting_code = fields.Char(
        string='Service Accounting Code',
        copy=False,
    )

    def _l10n_ae_pint_group_by_error_code(self):
        self.ensure_one()
        # ibr-184-ae/ibr-185-ae/ibr-186-ae: an item of type Goods needs the classification
        # identifier, Services needs the service accounting code, and Both needs one of each.
        # https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/rule/ibr-184-ae/ - https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/rule/ibr-185-ae/ - https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/rule/ibr-186-ae/
        item_type = self._l10n_ae_pint_get_item_type()
        if item_type in ('G', 'B') and not self.l10n_ae_classification_code:
            return (
                ("message", self.env._("Product(s) sold as goods should have their HS Code set.")),
                ("error_code", "l10n_ae_pint_product_classification_code_missing"),
                ("level", "danger"),
            )
        if item_type in ('S', 'B') and not self.l10n_ae_service_accounting_code:
            return (
                ("message", self.env._("Product(s) sold as services should have their Service Accounting Code set.")),
                ("error_code", "l10n_ae_pint_product_service_accounting_code_missing"),
                ("level", "danger"),
            )
        return False

    def _l10n_ae_pint_get_item_type(self):
        """Item type BTAE-13: 'B' for both, else 'S' for a service and 'G' for anything else."""
        self.ensure_one()
        if self.l10n_ae_is_good_and_service:
            return 'B'
        return 'S' if self.type == 'service' else 'G'

    def _l10n_ae_pint_action_text(self):
        # EXTENDS 'l10n.ae.pint.check.mixin'
        return self.env._("View Product(s)")
