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
        """Menu ids belonging to optional apps not enabled on ``env.company``.

        Listed xmlids and all their descendants are hidden so a root menu id
        (e.g. Comercios) also gates children that carry window actions.
        """
        if 'company.optional.app' not in self.env:
            return set()
        company = self.env.company.sudo()
        OptionalApp = self.env['company.optional.app'].sudo()
        all_apps = OptionalApp.search([])
        if not all_apps:
            return set()
        enabled = company.optional_app_ids
        disabled = all_apps - enabled
        roots = self.env['ir.ui.menu']
        for app in disabled:
            for xid in (app.menu_xmlids or '').split(','):
                xid = xid.strip()
                if not xid:
                    continue
                menu = self.env.ref(xid, raise_if_not_found=False)
                if menu:
                    roots |= menu
        if not roots:
            return set()
        Menu = self.env['ir.ui.menu'].sudo()
        domain = ['|'] * (len(roots) - 1) if len(roots) > 1 else []
        for root in roots:
            domain.append(('parent_path', '=like', f'{root.parent_path}%'))
        return set(Menu.search(domain).ids)
