# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.exceptions import UserError

from odoo.addons.point_of_sale.tests.common import CommonPosTest


@tagged('post_install', '-at_install')
class TestPointOfSale(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ignore pre-existing pricelists for the purpose of this test
        cls.env["product.pricelist"].search([]).write({"active": False})

        cls.company2 = cls.env.ref('base.test_company_template2')
        cls.company2.currency_id = cls.company_currency
        cls.pos_config_eur.write({
            'use_pricelist': False,
            'pricelist_id': False,
            'available_pricelist_ids': [Command.clear()],
        })
        cls.pricelist_eur.write({
            'active': True,
            'currency_id': cls.company_currency.id,
            'company_id': cls.company2.id,
            'sequence': 1,
        })
        # The two-company scenario needs one more pricelist than the shared setup.
        cls.company1_pricelist = cls.env["product.pricelist"].create({
            "name": "company 1 pricelist",
            "currency_id": cls.company_currency.id,
            "company_id": cls.company.id,
            "sequence": 2,
        })

        cls.product.write({'active': True, 'list_price': 100, 'taxes_id': [Command.clear()], 'available_in_pos': True})
        cls.product_combo = cls.env['product.combo'].create({
            'name': 'Product combo',
            'combo_item_ids': [Command.create({'product_id': cls.product.id, 'extra_price': 0})],
        })
        cls.size_attribute = cls.env.ref('product.pa_size')
        cls.size_values = cls.env['product.attribute.value'].create([
            {'name': 'Large', 'attribute_id': cls.size_attribute.id},
            {'name': 'Small', 'attribute_id': cls.size_attribute.id},
        ])

    def test_no_default_pricelist(self):
        """ Verify that the default pricelist isn't automatically set in the config """
        # Config creation is the operation under test.
        new_config = self.env["pos.config"].create({
            "name": "usd config", "available_pricelist_ids": [Command.set(self.company1_pricelist.ids)]
        })

        self.assertEqual(new_config.pricelist_id, self.env['product.pricelist'],
                         "POS config incorrectly has pricelist %s" % new_config.pricelist_id.display_name)

    def test_product_combo_variants(self):
        # Add attribute and values, simulating variant creation
        original_product_id = self.product.id
        self.product.product_tmpl_id.with_context(create_product_product=True).write({
            'attribute_line_ids': [(0, 0, {
                'attribute_id': self.size_attribute.id,
                'value_ids': [Command.set(self.size_values.ids)],
            })],
        })
        # Check that original product should not be in combo anymore (replace by variants)
        self.assertTrue(original_product_id not in self.product_combo.combo_item_ids.mapped('product_id').ids, "Original product should not be in combo")

    def test_pos_bill_digits(self):
        coin = self.env.ref('point_of_sale.0_05')
        coin.value = 0.005
        self.assertEqual(coin.value, 0.005)

    def test_session_filter_local_data(self):
        products = (
            self.ten_dollars_no_tax | self.twenty_dollars_no_tax
            | self.ten_dollars_with_5_incl | self.twenty_dollars_with_5_incl
        ).with_context(tracking_disable=True)
        product1, product2, product3, product4 = products
        # Prepare the fixture without notifying other open self-order sessions.
        products._write({'available_in_pos': False})
        config = self.pos_config_usd
        session = self.open_new_session(config=config)

        # Delete one product and archive another one
        products_to_display = [product1.id, product2.id, product3.id]
        product1.write({'active': False})
        product2.unlink()
        models_to_filter = {'product.template': products_to_display}
        products_to_display = list(set(products_to_display) - set(session.filter_local_data(models_to_filter)['product.template']))
        self.assertEqual(products_to_display, [product3.id])

        # No change
        products_to_display = [product3.id, product4.id]
        models_to_filter = {'product.template': products_to_display}
        products_to_display = list(set(products_to_display) - set(session.filter_local_data(models_to_filter)['product.template']))
        self.assertEqual(sorted(products_to_display), sorted([product3.id, product4.id]))

        # Delete all products
        products_to_display = [product3.id, product4.id]
        product3.unlink()
        product4.unlink()
        models_to_filter = {'product.template': products_to_display}
        products_to_display = list(set(products_to_display) - set(session.filter_local_data(models_to_filter)['product.template']))
        self.assertEqual(products_to_display, [])

        # Cannot archive config while session is active
        with self.assertRaises(UserError):
            config.write({'active': False})
