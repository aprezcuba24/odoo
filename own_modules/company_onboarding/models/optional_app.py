# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CompanyOptionalApp(models.Model):
    _name = 'company.optional.app'
    _description = 'Aplicación opcional por compañía'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help='Identificador estable (p. ej. payment_gateway).',
    )
    menu_xmlids = fields.Text(
        string='XML IDs de menú',
        help='Xmlids de ir.ui.menu separados por coma. Sin dependencia al módulo de la app.',
    )

    _code_uniq = models.Constraint(
        'unique(code)',
        'Ya existe una aplicación opcional con ese código.',
    )
