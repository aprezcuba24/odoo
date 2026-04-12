# Part of Odoo. See LICENSE file for full copyright and licensing details.

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
    return ProductListRow(
        id=product.id,
        name=product.display_name,
        default_code=product.default_code,
        list_price=float(product.lst_price),
        uom_name=product.uom_id.name if product.uom_id else None,
        barcode=product.barcode,
        category=_category_from_template(product.product_tmpl_id),
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
    return SaleOrderLineOut(
        product_id=line.product_id.id,
        name=line.name,
        qty=float(line.product_uom_qty),
        price_unit=float(line.price_unit),
        price_subtotal=float(line.price_subtotal),
        qty_delivered=float(line.qty_delivered),
        qty_reserved=_sale_order_line_qty_reserved(line),
    )


def sale_order_to_summary(order):
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
    )


def sale_order_to_detail_response(order):
    lines = order.order_line.filtered(lambda l: not l.display_type)
    summary = sale_order_to_summary(order)
    return SaleOrderDetailResponse.model_validate({
        **summary.model_dump(),
        'lines': [sale_order_line_to_response(line) for line in lines],
    })


def sale_order_to_created_response(order):
    return OrderCreatedResponse(
        id=order.id,
        name=order.name,
        order_ref=order.order_bridge_ref,
        state=order.state,
        device_validated=order.order_bridge_device_validated,
        delivery_address=delivery_address_from_record(order.order_bridge_snapshot_address_id),
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
