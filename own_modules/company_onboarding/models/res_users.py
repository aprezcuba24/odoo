# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    company_onboarding_state = fields.Selection(
        selection=[
            ('pending', 'Pendiente'),
            ('done', 'Completado'),
        ],
        string='Estado onboarding compañía',
        default='done',
        copy=False,
        help='Los usuarios nuevos vía signup quedan en pendiente hasta crear su compañía.',
    )

    def _is_company_onboarding_pending(self):
        self.ensure_one()
        return self.company_onboarding_state == 'pending'

    @api.model
    def _signup_create_user(self, values):
        """Crear usuario interno pendiente de onboarding (no portal)."""
        user = super()._signup_create_user(values)
        group_user = self.env.ref('base.group_user')
        user.sudo().write({
            'company_onboarding_state': 'pending',
            'group_ids': [(6, 0, [group_user.id])],
            'share': False,
            'action_id': self.env.ref(
                'company_onboarding.action_company_onboarding_wizard'
            ).id,
        })
        return user

    def _on_webclient_bootstrap(self):
        super()._on_webclient_bootstrap()
        # Soft gate: keep home action pointed at the wizard while pending.
        if self._is_company_onboarding_pending():
            action = self.env.ref(
                'company_onboarding.action_company_onboarding_wizard',
                raise_if_not_found=False,
            )
            if action and self.action_id != action:
                self.sudo().write({'action_id': action.id})
