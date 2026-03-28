# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Upgrade databases from ``mobile_order`` (19.0.1.x) naming to ``order_bridge``.

Renames the module row, metadata, ORM registry rows, and PostgreSQL columns/tables
so the 19.0.2 codebase loads without duplicate models or missing columns.

If this database was never ``mobile_order``, most steps no-op (guarded).
"""


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return cr.fetchone() is not None


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def migrate(cr, version):
    # Module technical name (directory) must match for Odoo to load the addon.
    cr.execute("UPDATE ir_module_module SET name = %s WHERE name = %s", ('order_bridge', 'mobile_order'))
    cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", ('order_bridge', 'mobile_order'))

    # ir.model: device model
    cr.execute(
        "UPDATE ir_model SET model = %s WHERE model = %s",
        ('order_bridge.device', 'mobile.device'),
    )
    cr.execute(
        """
        UPDATE ir_model_data SET name = %s
        WHERE module = 'order_bridge' AND name = %s AND model = 'ir.model'
        """,
        ('model_order_bridge_device', 'model_mobile_device'),
    )

    # Device table
    if _table_exists(cr, 'mobile_device') and not _table_exists(cr, 'order_bridge_device'):
        cr.execute("ALTER TABLE mobile_device RENAME TO order_bridge_device")

    # sale.order columns
    renames_sale = [
        ('mobile_origin', 'order_bridge_origin'),
        ('mobile_device_id', 'order_bridge_device_id'),
        ('mobile_device_validated', 'order_bridge_device_validated'),
        ('mobile_order_ref', 'order_bridge_ref'),
        ('mobile_pos_config_id', 'order_bridge_pos_config_id'),
    ]
    for old, new in renames_sale:
        if _column_exists(cr, 'sale_order', old) and not _column_exists(cr, 'sale_order', new):
            cr.execute(
                'ALTER TABLE sale_order RENAME COLUMN {} TO {}'.format(old, new),
            )

    # res.company
    if _column_exists(cr, 'res_company', 'mobile_pos_config_id') and not _column_exists(
        cr, 'res_company', 'order_bridge_pos_config_id'
    ):
        cr.execute(
            'ALTER TABLE res_company RENAME COLUMN mobile_pos_config_id TO order_bridge_pos_config_id',
        )

    # res.partner (stored computed)
    renames_partner = [
        ('mobile_app_registered', 'order_bridge_registered'),
        ('mobile_phone_validated', 'order_bridge_phone_validated'),
    ]
    for old, new in renames_partner:
        if _column_exists(cr, 'res_partner', old) and not _column_exists(cr, 'res_partner', new):
            cr.execute('ALTER TABLE res_partner RENAME COLUMN {} TO {}'.format(old, new))

    # ir.model.fields (model name string + relation targets)
    cr.execute(
        "UPDATE ir_model_fields SET model = %s WHERE model = %s",
        ('order_bridge.device', 'mobile.device'),
    )
    cr.execute(
        "UPDATE ir_model_fields SET relation = %s WHERE relation = %s",
        ('order_bridge.device', 'mobile.device'),
    )

    field_renames = [
        ('sale.order', 'mobile_origin', 'order_bridge_origin'),
        ('sale.order', 'mobile_device_id', 'order_bridge_device_id'),
        ('sale.order', 'mobile_device_validated', 'order_bridge_device_validated'),
        ('sale.order', 'mobile_order_ref', 'order_bridge_ref'),
        ('sale.order', 'mobile_pos_config_id', 'order_bridge_pos_config_id'),
        ('res.company', 'mobile_pos_config_id', 'order_bridge_pos_config_id'),
        ('res.partner', 'mobile_device_ids', 'order_bridge_device_ids'),
        ('res.partner', 'mobile_app_registered', 'order_bridge_registered'),
        ('res.partner', 'mobile_phone_validated', 'order_bridge_phone_validated'),
        ('res.partner', 'mobile_order_count', 'order_bridge_order_count'),
        ('res.config.settings', 'mobile_pos_config_id', 'order_bridge_pos_config_id'),
    ]
    for model, old_name, new_name in field_renames:
        cr.execute(
            """
            UPDATE ir_model_fields SET name = %s
            WHERE model = %s AND name = %s
            """,
            (new_name, model, old_name),
        )

    cr.execute(
        """
        UPDATE ir_model_fields SET related = %s
        WHERE model = 'res.config.settings' AND name = 'order_bridge_pos_config_id'
        """,
        ('company_id.order_bridge_pos_config_id',),
    )

    # ir_model_data: common XML ids
    xmlid_renames = [
        ('module_category_mobile_order', 'module_category_order_bridge'),
        ('group_mobile_order_user', 'group_order_bridge_user'),
        ('group_mobile_order_manager', 'group_order_bridge_manager'),
        ('seq_mobile_order_ref', 'seq_order_bridge_ref'),
        ('ir_config_parameter_mobile_inactivity_days', 'ir_config_parameter_order_bridge_inactivity_days'),
        ('ir_cron_mobile_device_inactive', 'ir_cron_order_bridge_device_inactive'),
        ('view_mobile_device_tree', 'view_order_bridge_device_tree'),
        ('view_mobile_device_form', 'view_order_bridge_device_form'),
        ('view_mobile_device_search', 'view_order_bridge_device_search'),
        ('action_mobile_device', 'action_order_bridge_device'),
        ('action_mobile_sale_orders', 'action_order_bridge_sale_orders'),
        ('action_mobile_partners', 'action_order_bridge_partners'),
        ('menu_mobile_order_root', 'menu_order_bridge_root'),
        ('menu_mobile_devices', 'menu_order_bridge_devices'),
        ('menu_mobile_orders', 'menu_order_bridge_orders'),
        ('menu_mobile_customers', 'menu_order_bridge_customers'),
        ('view_company_form_mobile_order', 'view_company_form_order_bridge'),
        ('res_config_settings_view_form_mobile_order', 'res_config_settings_view_form_order_bridge'),
        ('view_order_form_mobile_order', 'view_order_form_order_bridge'),
        ('view_order_tree_mobile_order', 'view_order_tree_order_bridge'),
        ('view_quotation_tree_mobile_order', 'view_quotation_tree_order_bridge'),
        ('view_partner_form_mobile_order', 'view_partner_form_order_bridge'),
        ('access_mobile_device_salesman', 'access_order_bridge_device_salesman'),
        ('access_mobile_device_user', 'access_order_bridge_device_user'),
        ('access_mobile_device_manager', 'access_order_bridge_device_manager'),
    ]
    for old, new in xmlid_renames:
        cr.execute(
            """
            UPDATE ir_model_data SET name = %s
            WHERE module = 'order_bridge' AND name = %s
            """,
            (new, old),
        )

    # Field XML ids (module.field_model__fieldname)
    field_xmlid_sql = [
        ('field_sale_order__mobile_origin', 'field_sale_order__order_bridge_origin'),
        ('field_sale_order__mobile_device_id', 'field_sale_order__order_bridge_device_id'),
        ('field_sale_order__mobile_device_validated', 'field_sale_order__order_bridge_device_validated'),
        ('field_sale_order__mobile_order_ref', 'field_sale_order__order_bridge_ref'),
        ('field_sale_order__mobile_pos_config_id', 'field_sale_order__order_bridge_pos_config_id'),
        ('field_res_company__mobile_pos_config_id', 'field_res_company__order_bridge_pos_config_id'),
        ('field_res_partner__mobile_device_ids', 'field_res_partner__order_bridge_device_ids'),
        ('field_res_partner__mobile_app_registered', 'field_res_partner__order_bridge_registered'),
        ('field_res_partner__mobile_phone_validated', 'field_res_partner__order_bridge_phone_validated'),
        ('field_res_partner__mobile_order_count', 'field_res_partner__order_bridge_order_count'),
        ('field_res_config_settings__mobile_pos_config_id', 'field_res_config_settings__order_bridge_pos_config_id'),
    ]
    for old, new in field_xmlid_sql:
        cr.execute(
            """
            UPDATE ir_model_data SET name = %s
            WHERE module = 'order_bridge' AND name = %s
            """,
            (new, old),
        )

    # Sequence + config
    cr.execute(
        """
        UPDATE ir_sequence SET code = %s, prefix = %s, name = %s
        WHERE code = %s
        """,
        ('order_bridge.order.ref', 'OB-', 'Order bridge reference', 'mobile.order.ref'),
    )
    cr.execute(
        """
        UPDATE ir_config_parameter SET key = %s
        WHERE key = %s
        """,
        ('order_bridge.device_inactivity_days', 'mobile_order.device_inactivity_days'),
    )

    # Window actions, messages, activities
    cr.execute(
        "UPDATE ir_act_window SET res_model = %s WHERE res_model = %s",
        ('order_bridge.device', 'mobile.device'),
    )
    cr.execute("UPDATE mail_message SET model = %s WHERE model = %s", ('order_bridge.device', 'mobile.device'))
    cr.execute(
        "UPDATE mail_activity SET res_model = %s WHERE res_model = %s",
        ('order_bridge.device', 'mobile.device'),
    )
    cr.execute(
        "UPDATE ir_attachment SET res_model = %s WHERE res_model = %s",
        ('order_bridge.device', 'mobile.device'),
    )
    cr.execute(
        "UPDATE mail_followers SET res_model = %s WHERE res_model = %s",
        ('order_bridge.device', 'mobile.device'),
    )

    cr.execute(
        "UPDATE ir_cron SET name = %s WHERE name = %s",
        ('Order bridge: deactivate inactive devices', 'Mobile: deactivate inactive devices'),
    )
