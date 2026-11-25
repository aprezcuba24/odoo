# Part of Odoo. See LICENSE file for full copyright and licensing details.


def merchant_store_product_domain(company):
    """Domain for catalog variants of active merchants in ``company``."""
    company.ensure_one()
    return [
        ('active', '=', True),
        ('sale_ok', '=', True),
        ('product_tmpl_id.merchant_id', '!=', False),
        ('product_tmpl_id.merchant_id.active', '=', True),
        ('product_tmpl_id.merchant_id.company_id', '=', company.id),
    ]


def merchant_store_app_enabled(company):
    """True unless ``company_onboarding`` is present and Comercios is off."""
    company.ensure_one()
    has_optional_app = getattr(company, 'has_optional_app', None)
    if callable(has_optional_app):
        return bool(has_optional_app('merchant_store'))
    return True
