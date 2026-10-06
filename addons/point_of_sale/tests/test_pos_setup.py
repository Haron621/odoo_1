# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo.exceptions import ValidationError
from odoo.addons.point_of_sale.tests.common import CommonPosTest


# TODO-PARP: Move tests and remove File

@odoo.tests.tagged('post_install', '-at_install')
class TestPoSSetup(CommonPosTest):
    """ This group of tests is for sanity check in setting up global records which will be used
    in each testing.

    If a test fails here, then it means there are inconsistencies in what we expect in the setup.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.config = cls.pos_config_usd
        cls.products = [
            cls.create_product('Product 1', cls.categ_basic, lst_price=10.0, standard_price=5),
            cls.create_product('Product 2', cls.categ_basic, lst_price=20.0, standard_price=10),
            cls.create_product('Product 3', cls.categ_basic, lst_price=30.0, standard_price=15),
        ]

    def test_basic_config_values(self):

        config = self.pos_config_usd
        self.assertEqual(config.currency_id, self.company_currency)
        self.assertFalse(config.use_pricelist)
        self.assertFalse(config.pricelist_id)

    def test_other_currency_config_values(self):
        config = self.pos_config_eur
        self.assertEqual(config.currency_id, self.other_currency)
        self.assertEqual(config.pricelist_id.currency_id, self.other_currency)

    def test_product_price(self):
        def get_price(pricelist, product):
            return pricelist._get_product_price(product, 1)


        # check usd pricelist
        pricelist = self.pos_config_usd.pricelist_id
        for product in self.products:
            self.assertAlmostEqual(get_price(pricelist, product), product.lst_price)

        # check eur pricelist
        # exchange rate to the other currency is set to 0.5, thus, lst_price
        # is expected to have half its original value.
        pricelist = self.pos_config_eur.pricelist_id
        for product in self.products:
            self.assertAlmostEqual(get_price(pricelist, product), product.lst_price * 0.5)

    def test_taxes(self):
        tax7 = self.taxes['tax7']
        self.assertAlmostEqual(tax7.amount, 7)
        self.assertFalse(tax7.price_include)
        tax10 = self.taxes['tax10']
        self.assertAlmostEqual(tax10.amount, 10)
        self.assertFalse(tax10.price_include)
        self.assertTrue(self.taxes['tax10_incl'].price_include)
        self.assertEqual(self.taxes['tax10_incl'].amount, 10)
        tax_group_7_10 = self.taxes['tax_group_7_10']
        self.assertEqual(tax_group_7_10.amount_type, 'group')
        self.assertEqual(sorted(tax_group_7_10.children_tax_ids.ids), sorted((tax7 | tax10).ids))

    def test_archive_used_journal(self):
        journal = self.env['account.journal'].create({
            'name': 'BANKOS',
            'company_id': self.company.id,
            'code': 'BANKOS',
            'type': 'bank',
            'invoice_reference_type': 'invoice',
            'invoice_reference_model': 'odoo'
        })
        payment_method = self.env['pos.payment.method'].create({
            'name': 'Lets Pay for Tests', 'journal_id': journal.id, 'type': 'bank'})
        self.pos_config_usd.write({'payment_method_ids': [odoo.Command.set(payment_method.ids)]})
        self.open_new_session()
        self.create_pos_order(
            [[self.products[0], 10]],
            payments=[[payment_method, 100]],
        )
        with self.assertRaises(ValidationError):
            journal.action_archive()

    def test_card_payment_method_initialization(self):
        """Test that the 'Card' payment method created by default has an outstanding account."""
        (self.bank_pm | self.bank_pm2).active = False
        _, payment_method_ids = self.pos_config_usd._create_journal_and_payment_methods()
        card_pm = self.env['pos.payment.method'].browse(payment_method_ids).filtered(lambda pm: pm.name == 'Card')
        self.assertTrue(card_pm)
        self.assertTrue(card_pm.outstanding_account_id)
