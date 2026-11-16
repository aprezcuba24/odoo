# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @tools.ormcache(
        'frozenset(self.env.user._get_group_ids())',
        'debug',
        'self.env.company.id',
    )
    def _visible_menu_ids(self, debug=False):
        """Hide optional-app menus when the current company has not enabled them."""
        visible = set(super()._visible_menu_ids(debug=debug))
        hidden = self._optional_app_hidden_menu_ids()
        if hidden:
            visible -= hidden
        return frozenset(visible)

    @api.model
    def _optional_app_hidden_menu_ids(self):
        """Menu ids belonging to optional apps not enabled on ``env.company``."""
        if 'company.optional.app' not in self.env:
            return set()
        company = self.env.company.sudo()
        OptionalApp = self.env['company.optional.app'].sudo()
        all_apps = OptionalApp.search([])
        if not all_apps:
            return set()
        enabled = company.optional_app_ids
        disabled = all_apps - enabled
        hidden = set()
        for app in disabled:
            for xid in (app.menu_xmlids or '').split(','):
                xid = xid.strip()
                if not xid:
                    continue
                menu = self.env.ref(xid, raise_if_not_found=False)
                if menu:
                    hidden.add(menu.id)
        return hidden
