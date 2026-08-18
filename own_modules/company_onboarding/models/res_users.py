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
        })
        return user
