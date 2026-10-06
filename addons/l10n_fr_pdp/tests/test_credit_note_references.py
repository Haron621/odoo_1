from lxml import etree

from odoo import fields
from odoo.tests import tagged

from .common import TestL10nFrPdpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCreditNoteReferences(TestL10nFrPdpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        model = cls.env['ir.model']._get('account.move')
        studio_fields = cls.env['ir.model.fields'].with_context(studio=True)
        studio_fields.create([
            {
                'name': name,
                'model_id': model.id,
                'ttype': field_type,
            }
            for name, field_type in (
                ('x_studio_peppol_contract_document_reference_id', 'char'),
                ('x_studio_peppol_invoice_previous_date', 'date'),
                ('x_studio_peppol_invoice_period_start_date', 'date'),
                ('x_studio_peppol_invoice_period_end_date', 'date'),
            )
            if name not in cls.env['account.move']._fields
        ])

    def _create_standalone_credit_note(self, **values):
        credit_note = self._create_french_invoice(move_type='out_refund', **values)
        credit_note.action_post()
        return credit_note

    def test_export_historical_credit_note(self):
        credit_note = self._create_standalone_credit_note(
            x_studio_peppol_contract_document_reference_id='PAPER-2020-0042',
            x_studio_peppol_invoice_previous_date='2020-04-15',
        )

        xml, errors = self.env['account.edi.xml.ubl_21_fr']._export_invoice(credit_note)
        tree = etree.fromstring(xml)

        self.assertFalse(errors)
        self.assertEqual(tree.findtext('./{*}CreditNoteTypeCode'), '381')
        self.assertEqual(
            tree.findtext('./{*}BillingReference/{*}InvoiceDocumentReference/{*}ID'),
            'PAPER-2020-0042',
        )
        self.assertEqual(
            tree.findtext('./{*}BillingReference/{*}InvoiceDocumentReference/{*}IssueDate'),
            '2020-04-15',
        )
        self.assertIsNone(tree.find('./{*}ContractDocumentReference'))

    def test_export_global_discount_credit_note(self):
        credit_note = self._create_standalone_credit_note(
            x_studio_peppol_contract_document_reference_id='REBATE-2024',
            x_studio_peppol_invoice_period_start_date='2024-01-01',
            x_studio_peppol_invoice_period_end_date='2024-12-31',
        )

        xml, errors = self.env['account.edi.xml.ubl_21_fr']._export_invoice(credit_note)
        tree = etree.fromstring(xml)

        self.assertFalse(errors)
        self.assertEqual(tree.findtext('./{*}CreditNoteTypeCode'), '262')
        self.assertEqual(
            tree.findtext('./{*}ContractDocumentReference/{*}ID'),
            'REBATE-2024',
        )
        self.assertEqual(tree.findtext('./{*}InvoicePeriod/{*}StartDate'), '2024-01-01')
        self.assertEqual(tree.findtext('./{*}InvoicePeriod/{*}EndDate'), '2024-12-31')
        self.assertIsNone(tree.find('./{*}BillingReference'))

    def test_reject_incomplete_or_conflicting_standalone_reference(self):
        credit_note = self._create_french_invoice(
            move_type='out_refund',
            x_studio_peppol_contract_document_reference_id='AMBIGUOUS',
            x_studio_peppol_invoice_previous_date='2020-04-15',
            x_studio_peppol_invoice_period_start_date='2024-01-01',
            x_studio_peppol_invoice_period_end_date='2024-12-31',
        )
        builder = self.env['account.edi.xml.ubl_21_fr']
        vals = builder._export_invoice_vals(credit_note)

        constraints = builder._export_invoice_constraints(credit_note, vals)

        self.assertIn('ubl_21_fr_refund_invoice_reference', constraints)

    def test_flow_10_maps_global_discount_to_credit_note(self):
        credit_note = self._create_standalone_credit_note(
            x_studio_peppol_contract_document_reference_id='REBATE-2024',
            x_studio_peppol_invoice_period_start_date='2024-01-01',
            x_studio_peppol_invoice_period_end_date='2024-12-31',
        )
        builder = self.env['pdp.flow.10.xml.builder']
        invoice_node = {}

        builder._invoice_add_referenced_documents(invoice_node, credit_note)

        self.assertEqual(builder._get_move_typecode(credit_note), '381')
        self.assertEqual(invoice_node['ReferencedDocument'], [{
            'ID': {'_text': 'REBATE-2024'},
            'IssueDate': {'_text': '20240101'},
        }])

    def test_import_ubl_credit_note_references(self):
        builder = self.env['account.edi.xml.ubl_21_fr']
        credit_note = self._create_french_invoice(move_type='in_refund')
        tree = etree.fromstring(b'''\
            <CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
                        xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                        xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
                <cbc:CreditNoteTypeCode>262</cbc:CreditNoteTypeCode>
                <cac:InvoicePeriod>
                    <cbc:StartDate>2024-01-01</cbc:StartDate>
                    <cbc:EndDate>2024-12-31</cbc:EndDate>
                </cac:InvoicePeriod>
                <cac:ContractDocumentReference><cbc:ID>REBATE-2024</cbc:ID></cac:ContractDocumentReference>
            </CreditNote>
        ''')

        builder._import_fill_invoice_form(credit_note, tree, 1)

        self.assertRecordValues(credit_note, [{
            'x_studio_peppol_contract_document_reference_id': 'REBATE-2024',
            'x_studio_peppol_invoice_previous_date': False,
            'x_studio_peppol_invoice_period_start_date': fields.Date.to_date('2024-01-01'),
            'x_studio_peppol_invoice_period_end_date': fields.Date.to_date('2024-12-31'),
        }])

    def test_import_facturx_credit_note_references(self):
        builder = self.env['account.edi.xml.cii']
        credit_note = self._create_french_invoice(move_type='in_refund')
        tree = etree.fromstring(b'''\
            <CrossIndustryInvoice xmlns="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                                  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
                                  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
                <ExchangedDocument><ram:TypeCode>381</ram:TypeCode></ExchangedDocument>
                <SupplyChainTradeTransaction>
                    <ram:ApplicableHeaderTradeSettlement>
                        <ram:InvoiceReferencedDocument>
                            <ram:IssuerAssignedID>PAPER-2020-0042</ram:IssuerAssignedID>
                            <ram:FormattedIssueDateTime>
                                <udt:DateTimeString format="102">20200415</udt:DateTimeString>
                            </ram:FormattedIssueDateTime>
                        </ram:InvoiceReferencedDocument>
                    </ram:ApplicableHeaderTradeSettlement>
                </SupplyChainTradeTransaction>
            </CrossIndustryInvoice>
        ''')

        self.assertEqual(builder._get_import_document_amount_sign(tree), ('refund', 1))
        builder._import_fill_invoice_form(credit_note, tree, 1)

        self.assertRecordValues(credit_note, [{
            'x_studio_peppol_contract_document_reference_id': 'PAPER-2020-0042',
            'x_studio_peppol_invoice_previous_date': fields.Date.to_date('2020-04-15'),
            'x_studio_peppol_invoice_period_start_date': False,
            'x_studio_peppol_invoice_period_end_date': False,
        }])

    def test_facturx_global_discount_is_imported_as_refund(self):
        builder = self.env['account.edi.xml.cii']
        credit_note = self._create_french_invoice(move_type='in_refund')
        tree = etree.fromstring(b'''\
            <CrossIndustryInvoice xmlns="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                                  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
                                  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
                <ExchangedDocument><ram:TypeCode>262</ram:TypeCode></ExchangedDocument>
                <SupplyChainTradeTransaction>
                    <ram:ApplicableHeaderTradeAgreement>
                        <ram:ContractReferencedDocument>
                            <ram:IssuerAssignedID>REBATE-2024</ram:IssuerAssignedID>
                        </ram:ContractReferencedDocument>
                    </ram:ApplicableHeaderTradeAgreement>
                    <ram:ApplicableHeaderTradeSettlement>
                        <ram:BillingSpecifiedPeriod>
                            <ram:StartDateTime>
                                <udt:DateTimeString format="102">20240101</udt:DateTimeString>
                            </ram:StartDateTime>
                            <ram:EndDateTime>
                                <udt:DateTimeString format="102">20241231</udt:DateTimeString>
                            </ram:EndDateTime>
                        </ram:BillingSpecifiedPeriod>
                    </ram:ApplicableHeaderTradeSettlement>
                </SupplyChainTradeTransaction>
            </CrossIndustryInvoice>
        ''')

        self.assertEqual(builder._get_import_document_amount_sign(tree), ('refund', 1))
        builder._import_fill_invoice_form(credit_note, tree, 1)

        self.assertRecordValues(credit_note, [{
            'x_studio_peppol_contract_document_reference_id': 'REBATE-2024',
            'x_studio_peppol_invoice_previous_date': False,
            'x_studio_peppol_invoice_period_start_date': fields.Date.to_date('2024-01-01'),
            'x_studio_peppol_invoice_period_end_date': fields.Date.to_date('2024-12-31'),
        }])
