from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestDonationProductTemplate(BaseCommon):
    def test_donation_product_can_be_archived(self):
        donation_product = self.env.ref("website_sale.product_donation")
        donation_product.write({"active": False})
        self.assertFalse(donation_product.active)

    def test_archived_donation_reactivated_on_order(self):
        donation_product = self.env.ref("website_sale.product_donation")
        donation_variant = donation_product.product_variant_id
        donation_product.write({"active": False})

        order = self.env["sale.order"].create({"partner_id": self.env.user.partner_id.id})
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": donation_variant.id,
        })

        self.assertTrue(donation_product.active)

    def test_archived_donation_in_order_line_product_picker(self):
        donation_product = self.env.ref("website_sale.product_donation")
        donation_variant = donation_product.product_variant_id
        donation_product.write({"active": False})

        domain = self.env["sale.order.line"]._domain_product_id()

        self.assertIn(donation_variant, self.env["product.product"].search(domain))

    def test_archived_donation_in_order_line_template_picker(self):
        donation_product = self.env.ref("website_sale.product_donation")
        donation_product.write({"active": False})

        domain = self.env["sale.order.line"]._domain_product_template_id()

        self.assertIn(donation_product, self.env["product.template"].search(domain))

    def test_donation_product_can_not_be_deleted(self):
        donation_product = self.env.ref("website_sale.product_donation")
        self.assertRaises(UserError, donation_product.unlink)
