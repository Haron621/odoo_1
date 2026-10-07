# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os

import xapian

from odoo.tools import config


class Opian:
    termgenerator = xapian.TermGenerator()
    termgenerator.set_stemmer(xapian.Stem("en"))

    def __init__(self, dbname, index="mail_message"):
        self.dbpath = os.path.join(config.filestore(dbname), "xapian", index)
        os.makedirs(self.dbpath, exist_ok=True)
        self.writableDb = xapian.WritableDatabase(self.dbpath, xapian.DB_CREATE_OR_OPEN)

    def index(self, record_id, value):
        # index data into the database
        id_term = f"Q{record_id}"
        doc = xapian.Document()
        self.termgenerator.set_document(doc)
        self.termgenerator.index_text(value)
        doc.set_data(str(record_id))
        doc.add_boolean_term(id_term)
        self.writableDb.replace_document(id_term, doc)

    def query(self):
        # Query the database "somehow"
