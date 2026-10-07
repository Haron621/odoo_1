-- disable Bancontact Payment POS integration
UPDATE pos_bancontact_product
   SET test_mode = true,
       refund_enabled = false;

-- remove the Bancontact Pay signing keys
UPDATE res_company
   SET bancontact_signing_key = NULL,
       bancontact_signing_kid = NULL;
