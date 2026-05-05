# Part of Odoo. See LICENSE file for full copyright and licensing details.


def extend_domain_from_int_params(domain, params, query_param_key, field_name, operator):
    raw = params.get(query_param_key)
    if not raw:
        return
    try:
        value = int(raw)
    except ValueError:
        return
    domain.append((field_name, operator, value))
