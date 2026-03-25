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
# def extend_domain_from_int_params(domain, params, specs):
#     """Append domain leaves from optional query params parsed as integers.

#     For each (param_key, field_name, operator) in specs: if params[param_key]
#     is truthy, try int(raw) and append (field_name, operator, value) to domain.
#     On ValueError (invalid int), the spec is skipped.

#     :param domain: list to mutate in place
#     :param params: mapping with .get (e.g. request.params)
#     :param specs: iterable of (param_key, field_name, operator) triples
#     """
#     for param_key, field_name, operator in specs:
#         raw = params.get(param_key)
#         if not raw:
#             continue
#         try:
#             value = int(raw)
#         except ValueError:
#             continue
#         domain.append((field_name, operator, value))
