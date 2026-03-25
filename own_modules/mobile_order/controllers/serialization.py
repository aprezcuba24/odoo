# Part of Odoo. See LICENSE file for full copyright and licensing details.


def serialize_many(records, fn, /, **kwargs):
    """Map a recordset or iterable of records to a list of dicts."""
    return [fn(record, **kwargs) for record in records]


def serialize_one(record, fn, /, **kwargs):
    """Serialize a single record to a dict."""
    return fn(record, **kwargs)


def _pos_categories_payload(pos_categ_ids):
    return [{'id': c.id, 'name': c.name} for c in pos_categ_ids]


def pos_category_to_mobile_dict(c):
    return {
        'id': c.id,
        'name': c.name,
        'parent_id': c.parent_id.id if c.parent_id else None,
    }


def product_product_to_mobile_dict(p, *, include_description_sale=False):
    d = {
        'id': p.id,
        'name': p.display_name,
        'default_code': p.default_code,
        'list_price': p.lst_price,
        'uom_name': p.uom_id.name if p.uom_id else None,
        'barcode': p.barcode,
        'pos_categories': _pos_categories_payload(p.product_tmpl_id.pos_categ_ids),
    }
    if include_description_sale:
        d['description_sale'] = p.description_sale
    return d
