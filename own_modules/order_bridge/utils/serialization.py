# Part of Odoo. See LICENSE file for full copyright and licensing details.

from urllib.parse import urlparse

from odoo.http import request

from ..schemas.responses import (
    CategoriesListResponse,
    DeliveryAddressOut,
    GeneralSettingsResponse,
    MunicipalitiesListResponse,
    MunicipalityWithNeighborhoodsRow,
    NeighborhoodRow,
    OrderCancelResponse,
    OrderCreatedResponse,
    OrdersPageResponse,
    ProductCategoryRow,
    ProductDetailResponse,
    ProductListRow,
    ProductsPageResponse,
    ProfileAddressOut,
    ProfileResponse,
    SaleOrderDetailResponse,
    SaleOrderLineOut,
    SaleOrderSummary,
)


def delivery_address_from_record(addr):
    """Map `order_bridge.partner_address` or snapshot to API shape."""
    if not addr:
        return None
    return DeliveryAddressOut(
        street=addr.street or '',
        municipality_id=addr.municipality_id.id if addr.municipality_id else None,
        municipality_name=addr.municipality_id.name if addr.municipality_id else None,
        neighborhood_id=addr.neighborhood_id.id if addr.neighborhood_id else None,
        neighborhood_name=addr.neighborhood_id.name if addr.neighborhood_id else None,
        state=addr.state or '',
    )


def _category_from_template(tmpl):
    c = tmpl.categ_id
    if not c:
        return None
    return ProductCategoryRow(
        id=c.id,
        name=c.name,
        parent_id=c.parent_id.id if c.parent_id else None,
    )


def product_category_to_response(category):
    return ProductCategoryRow(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id.id if category.parent_id else None,
    )


def _order_bridge_url_host_is_loopback(url: str) -> bool:
    """True if URL host is localhost / loopback (not reachable from another device)."""
    if not url:
        return True
    try:
        host = (urlparse(url).hostname or '').lower()
    except ValueError:
        return True
    if not host:
        return True
    if host in ('localhost', '::1', '0.0.0.0'):
        return True
    if host.startswith('127.'):
        return True
    return False


def _order_bridge_public_base_url():
    """Base URL for absolute image links in JSON.

    Prefer the URL the **current** client used to call the API (``url_root``) so phones
    and browsers on another network get hosts they can reach. ``web.base.url`` is only
    preferred when the request URL is loopback (e.g. local admin) but ICP points to a
    public URL.
    """
    url_root = request.httprequest.url_root.rstrip('/')
    icp = (request.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')

    if not _order_bridge_url_host_is_loopback(url_root):
        return url_root
    if icp and not _order_bridge_url_host_is_loopback(icp):
        return icp
    return url_root or icp


def _product_image_urls(product):
    """Absolute URLs for ``/web/image`` (requires ``_can_return_content`` on ``product.product``).

    Use variant or template binary fields so URLs appear even if ``image_1920`` was not
    recomputed yet on the variant after a batch ``search`` (image often lives on template).
    """
    tmpl = product.product_tmpl_id
    if not (product.image_variant_1920 or tmpl.image_1920):
        return None, None
    base = _order_bridge_public_base_url()
    pid = product.id
    return (
        f'{base}/web/image/product.product/{pid}/image_512',
        f'{base}/web/image/product.product/{pid}/image_128',
    )


def categories_list_response(categories):
    rows = [product_category_to_response(c) for c in categories]
    return CategoriesListResponse(items=rows, total=len(rows))


def general_settings_response(record):
    return GeneralSettingsResponse(shop_phone=record.shop_phone)


def municipalities_list_response(municipalities):
    items = []
    for m in municipalities:
        n_rows = [
            NeighborhoodRow(id=n.id, name=n.name)
            for n in m.neighborhood_ids.filtered('active').sorted('name')
        ]
        items.append(
            MunicipalityWithNeighborhoodsRow(id=m.id, name=m.name, neighborhoods=n_rows),
        )
    return MunicipalitiesListResponse(items=items, total=len(items))


def product_to_list_row(product):
    image_url, thumb_url = _product_image_urls(product)
    return ProductListRow(
        id=product.id,
        name=product.display_name,
        default_code=product.default_code,
        list_price=float(product.lst_price),
        uom_name=product.uom_id.name if product.uom_id else None,
        barcode=product.barcode,
        category=_category_from_template(product.product_tmpl_id),
        image_url=image_url,
        image_thumbnail_url=thumb_url,
    )


def product_to_detail_response(product):
    base = product_to_list_row(product).model_dump()
    return ProductDetailResponse.model_validate({
        **base,
        'description_sale': product.description_sale,
    })


def products_page_response(products, limit, offset, total):
    items = [product_to_list_row(p) for p in products]
    return ProductsPageResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    )


def order_bridge_profile_to_response(partner, device):
    """Profile payload for GET/PUT/PATCH `/api/order_bridge/profile`."""
    partner.ensure_one()
    device.ensure_one()
    addr = (
        partner.env['order_bridge.partner_address']
        .sudo()
        .search([('partner_id', '=', partner.id)], limit=1)
    )
    da = delivery_address_from_record(addr) if addr else None
    address = (
        ProfileAddressOut.model_validate(da.model_dump()) if da else None
    )
    return ProfileResponse(
        id=partner.id,
        name=partner.name,
        phone=partner.phone or device.phone or '',
        email=partner.email,
        address=address,
    )


def _sale_order_line_qty_reserved(line):
    """Quantity reserved on stock moves for this line (not done), in line UoM."""
    if not line.product_id.is_storable:
        return 0.0
    total = 0.0
    for move in line.move_ids:
        if move.state in ('done', 'cancel'):
            continue
        for ml in move.move_line_ids:
            total += ml.product_uom_id._compute_quantity(
                ml.quantity, line.product_uom_id, rounding_method='HALF-UP'
            )
    return total


def sale_order_line_to_response(line):
    image_url, thumb_url = (None, None)
    if line.product_id:
        image_url, thumb_url = _product_image_urls(line.product_id)
    return SaleOrderLineOut(
        product_id=line.product_id.id,
        name=line.name,
        qty=float(line.product_uom_qty),
        price_unit=float(line.price_unit),
        price_subtotal=float(line.price_subtotal),
        qty_delivered=float(line.qty_delivered),
        qty_reserved=_sale_order_line_qty_reserved(line),
        image_url=image_url,
        image_thumbnail_url=thumb_url,
    )


def _infer_delivery_status_from_lines(order):
    """When ``sale_stock`` leaves ``delivery_status`` empty (no pickings, all cancelled, etc.).

    Infer *partial* / *full* from line quantities so the API still reflects delivered goods.
    """
    if order.state not in ('sale', 'done'):
        return None
    lines = order.order_line.filtered(
        lambda l: not l.display_type and not l.is_downpayment and l.product_id
    )
    if not lines:
        return None
    total = 0.0
    delivered = 0.0
    for line in lines:
        total += line.product_uom_qty
        delivered += line.qty_delivered
    if delivered <= 0 or total <= 0:
        return None
    if delivered + 1e-9 >= total:
        return 'full'
    return 'partial'


def _effective_date_iso(order):
    """ISO datetime for first customer delivery; fallback to done pickings if field is empty."""
    ed = order.effective_date
    if ed:
        return ed.isoformat()
    pickings = order.picking_ids.filtered(
        lambda p: p.state == 'done' and p.location_dest_id.usage == 'customer'
    )
    dates = [p.date_done for p in pickings if p.date_done]
    if not dates:
        return None
    return min(dates).isoformat()


def _delivery_fields_from_order(order):
    """Map sale_stock ``delivery_status`` / ``effective_date`` for API (False → None).

    If Odoo leaves ``delivery_status`` empty but lines show deliveries, infer *partial* / *full*.
    """
    ds = order.delivery_status or _infer_delivery_status_from_lines(order)
    delivery_status = ds if ds else None
    effective_date = _effective_date_iso(order)
    return delivery_status, effective_date


def sale_order_to_summary(order):
    delivery_status, effective_date = _delivery_fields_from_order(order)
    return SaleOrderSummary(
        id=order.id,
        name=order.name,
        order_ref=order.order_bridge_ref,
        origin=order.order_bridge_origin,
        state=order.state,
        date_order=order.date_order.isoformat() if order.date_order else None,
        amount_total=float(order.amount_total),
        currency=order.currency_id.name if order.currency_id else None,
        device_validated=order.order_bridge_device_validated,
        delivery_address=delivery_address_from_record(order.order_bridge_snapshot_address_id),
        delivery_status=delivery_status,
        effective_date=effective_date,
    )


def sale_order_to_detail_response(order):
    lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
    summary = sale_order_to_summary(order)
    return SaleOrderDetailResponse.model_validate({
        **summary.model_dump(),
        'lines': [sale_order_line_to_response(line) for line in lines],
    })


def sale_order_to_created_response(order):
    delivery_status, effective_date = _delivery_fields_from_order(order)
    return OrderCreatedResponse(
        id=order.id,
        name=order.name,
        order_ref=order.order_bridge_ref,
        state=order.state,
        device_validated=order.order_bridge_device_validated,
        delivery_address=delivery_address_from_record(order.order_bridge_snapshot_address_id),
        delivery_status=delivery_status,
        effective_date=effective_date,
    )


def orders_page_response(orders, limit, offset, total):
    items = [sale_order_to_summary(o) for o in orders]
    return OrdersPageResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    )


def order_cancel_response(order):
    return OrderCancelResponse(id=order.id, state=order.state)
