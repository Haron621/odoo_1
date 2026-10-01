from odoo.http import Controller, request, route
from odoo.release import version_info


class Documentation(Controller):

    @staticmethod
    def getAbsoluteLink(target=''):
        """
        Get the full link to the odoo documentation corresponding to the version of the database.
        """
        version = (version_info[0] + "." + version_info[1]).replace("~", "-") if version_info[3] == 'FINAL' else "master"
        return f"https://www.odoo.com/documentation/{version}/{target}"

    @route(
        ['/web/documentation/open/', '/web/documentation/open/<path:target>'],
        type='http', auth='user', readonly=True, methods=['GET'],
    )
    def open(self, target=''):
        """
        Redirect to the odoo documentation corresponding to the version of the database.
        """
        return request.redirect(Documentation.getAbsoluteLink(target), local=False)
