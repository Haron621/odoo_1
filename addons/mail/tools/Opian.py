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

    def index(self, id, value):
        # index data into the database
        doc = xapian.Document()
        self.termgenerator.set_document(doc)
        self.termgenerator.index_text(value)
        doc.add_boolean_term(id)
        self.writableDb.replace_document(id, doc)

    def query(self):
        # Query the database "somehow"
