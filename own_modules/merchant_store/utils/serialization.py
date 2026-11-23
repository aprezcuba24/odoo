# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.order_bridge.utils.serialization import (
    _order_bridge_public_base_url,
    _product_image_urls,
)

from ..schemas.responses import (
    CheckoutCreatedResponse,
    MerchantOrderDetailResponse,
    MerchantOrderLineOut,
    MerchantOrdersPageResponse,
    MerchantOrderSummary,
    MerchantProductDetailResponse,
    MerchantProductListRow,
    MerchantProductsPageResponse,
    MerchantRow,
    MerchantsListResponse,
)


def _merchant_logo_urls(merchant):
    if not merchant.logo:
        return None, None
    base = _order_bridge_public_base_url()
    mid = merchant.id
    return (
        f'{base}/web/image/merchant_store.merchant/{mid}/logo/512x0',
        f'{base}/web/image/merchant_store.merchant/{mid}/logo/128x128',
    )


def merchant_to_row(merchant):
    logo_url, thumb_url = _merchant_logo_urls(merchant)
    return MerchantRow(
        id=merchant.id,
        name=merchant.name,
        description=merchant.description,
        logo_url=logo_url,
        logo_thumbnail_url=thumb_url,
    )


def merchants_list_response(merchants):
    rows = [merchant_to_row(m) for m in merchants]
    return MerchantsListResponse(items=rows, total=len(rows))


def product_to_list_row(product):
    image_url, thumb_url = _product_image_urls(product)
    return MerchantProductListRow(
        id=product.id,
        name=product.display_name,
        list_price=float(product.lst_price),
        merchant_id=product.product_tmpl_id.merchant_id.id,
        uom_name=product.uom_id.name if product.uom_id else None,
        image_url=image_url,
        image_thumbnail_url=thumb_url,
    )


def product_to_detail_response(product):
    base = product_to_list_row(product).model_dump()
    return MerchantProductDetailResponse.model_validate({
        **base,
        'description_sale': product.description_sale,
    })


def products_page_response(products, limit, offset, total):
    return MerchantProductsPageResponse(
        items=[product_to_list_row(p) for p in products],
        limit=limit,
        offset=offset,
        total=total,
    )


def sale_order_line_to_response(line):
    image_url, thumb_url = (None, None)
    if line.product_id:
        image_url, thumb_url = _product_image_urls(line.product_id)
    return MerchantOrderLineOut(
        product_id=line.product_id.id,
        name=line.name,
        qty=float(line.product_uom_qty),
        price_unit=float(line.price_unit),
        price_subtotal=float(line.price_subtotal),
        image_url=image_url,
        image_thumbnail_url=thumb_url,
    )


def sale_order_to_summary(order):
    return MerchantOrderSummary(
        id=order.id,
        name=order.name,
        merchant_id=order.merchant_id.id,
        client_checkout_id=order.client_checkout_id,
        order_bridge_order_id=order.order_bridge_order_id.id if order.order_bridge_order_id else None,
        state=order.state,
        store_state=order.order_bridge_store_state or 'reviewing',
        date_order=order.date_order.isoformat() if order.date_order else None,
        amount_total=float(order.amount_total),
        currency=order.currency_id.name if order.currency_id else None,
    )


def sale_order_to_detail_response(order):
    lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
    summary = sale_order_to_summary(order)
    return MerchantOrderDetailResponse.model_validate({
        **summary.model_dump(),
        'lines': [sale_order_line_to_response(line) for line in lines],
    })


def orders_page_response(orders, limit, offset, total):
    return MerchantOrdersPageResponse(
        items=[sale_order_to_summary(o) for o in orders],
        limit=limit,
        offset=offset,
        total=total,
    )


def checkout_created_response(orders, client_checkout_id):
    return CheckoutCreatedResponse(
        client_checkout_id=client_checkout_id,
        orders=[sale_order_to_detail_response(o) for o in orders],
    )
