# Part of Odoo. See LICENSE file for full copyright and licensing details.


def serialize_many(records, fn, /, **kwargs):
    """Map a recordset or iterable of records to a list of dicts."""
    return [fn(record, **kwargs) for record in records]


def serialize_one(record, fn, /, **kwargs):
    """Serialize a single record to a dict."""
    return fn(record, **kwargs)


def _pos_categories_payload(pos_categ_ids):
    return [{'id': c.id, 'name': c.name} for c in pos_categ_ids]


def pos_category_to_api_dict(c):
    return {
        'id': c.id,
        'name': c.name,
        'parent_id': c.parent_id.id if c.parent_id else None,
    }


def product_product_to_api_dict(p, *, include_description_sale=False):
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


def serialize_pagination(items, limit, offset, total, pos_config_id=None):
    payload = {
        'items': items,
        'limit': limit,
        'offset': offset,
        'total': total,
    }
    if pos_config_id is not None:
        payload['pos_config_id'] = pos_config_id
    return payload


def sale_order_line_to_api_dict(line):
    return {
        'product_id': line.product_id.id,
        'name': line.name,
        'qty': line.product_uom_qty,
        'price_unit': line.price_unit,
        'price_subtotal': line.price_subtotal,
    }


def sale_order_to_api_dict(order, *, lines=False):
    base = {
        'id': order.id,
        'name': order.name,
        'order_ref': order.order_bridge_ref,
        'origin': order.order_bridge_origin,
        'state': order.state,
        'date_order': order.date_order.isoformat() if order.date_order else None,
        'amount_total': order.amount_total,
        'currency': order.currency_id.name if order.currency_id else None,
        'device_validated': order.order_bridge_device_validated,
    }
    if lines:
        order_lines = order.order_line.filtered(lambda l: not l.display_type)
        base['lines'] = serialize_many(order_lines, sale_order_line_to_api_dict)
    return base


def sale_order_created_to_api_dict(order):
    return {
        'id': order.id,
        'name': order.name,
        'order_ref': order.order_bridge_ref,
        'state': order.state,
        'device_validated': order.order_bridge_device_validated,
    }
