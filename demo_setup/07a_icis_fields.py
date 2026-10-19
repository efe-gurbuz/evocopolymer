"""
07a_icis_fields.py
ICIS integration - PLAN A: Studio-style custom x_ fields on
product.template and purchase.order.line, created the same way Studio
itself would (direct ir.model.fields records), plus view inheritance to
show them, plus the "ICIS Piyasa Fiyatları" act_url menu.

Idempotent: search-before-create for fields/views/menu/action.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/07a_icis_fields.py
"""

print("=" * 70)
print("07a_icis_fields.py starting")
print("=" * 70)

IMF = env['ir.model.fields'].sudo()
IModel = env['ir.model'].sudo()
View = env['ir.ui.view'].sudo()
Menu = env['ir.ui.menu'].sudo()
Action = env['ir.actions.act_url'].sudo()


def get_model_id(model_name):
    m = IModel.search([('model', '=', model_name)], limit=1)
    assert m, f"model not found: {model_name}"
    return m.id


def get_or_create_field(model_name, name, vals):
    existing = IMF.search([('model', '=', model_name), ('name', '=', name)], limit=1)
    if existing:
        # self-healing: correct description/help if the field was created
        # by an earlier run before a requirement (e.g. the PO-currency
        # rule's help text) existed.
        fix_vals = {k: v for k, v in vals.items()
                    if k in ('field_description', 'help') and getattr(existing, k, None) != v}
        if fix_vals:
            existing.write(fix_vals)
            print(f"  [FIX] field updated: {model_name}.{name} -> {list(fix_vals.keys())}")
        else:
            print(f"  [SKIP] field exists: {model_name}.{name}")
        return existing
    vals = dict(vals, model_id=get_model_id(model_name), name=name)
    f = IMF.create(vals)
    print(f"  [OK] field created: {model_name}.{name}")
    return f


# --- product.template custom fields ---
get_or_create_field('product.template', 'x_icis_url', {
    'field_description': 'ICIS URL',
    'ttype': 'char',
})
get_or_create_field('product.template', 'x_icis_ref_price', {
    'field_description': 'ICIS Referans Fiyatı (USD/kg)',
    'ttype': 'float',
})
get_or_create_field('product.template', 'x_icis_price_date', {
    'field_description': 'ICIS Fiyat Tarihi',
    'ttype': 'date',
})

# --- purchase.order.line custom fields ---
get_or_create_field('purchase.order.line', 'x_icis_url', {
    'field_description': 'ICIS URL',
    'ttype': 'char',
    'related': 'product_id.product_tmpl_id.x_icis_url',
    'readonly': True,
})
get_or_create_field('purchase.order.line', 'x_icis_price', {
    'field_description': 'ICIS Fiyatı',
    'ttype': 'float',
    # audit point 12: the ICIS price is entered in the PO's OWN currency
    # (order_id.currency_id) - never converted - exactly like price_unit
    # on the same line, so the variance% comparison is always apples-to-
    # apples without any hidden FX conversion.
    'help': 'ICIS referans fiyatı, satın alma siparişinin kendi para '
            'biriminde girilir (price_unit ile aynı para birimi, '
            'dönüştürme yapılmaz).',
})
get_or_create_field('purchase.order.line', 'x_icis_variance_pct', {
    'field_description': 'ICIS Sapma (%)',
    'ttype': 'float',
    'help': '(Birim fiyat - ICIS fiyatı) / ICIS fiyatı x 100. Otomasyon kuralıyla hesaplanır.',
})

env.cr.commit()

# -----------------------------------------------------------------------
# View inheritance: show the new fields
# -----------------------------------------------------------------------
product_form = env.ref('product.product_template_form_view')
view_name = "Areks Demo - ICIS fields on product form"
if not View.search([('name', '=', view_name)], limit=1):
    View.create({
        'name': view_name,
        'model': 'product.template',
        'inherit_id': product_form.id,
        'arch_db': """
            <xpath expr="//page[@name='purchase']" position="inside">
                <group string="ICIS Piyasa Verisi">
                    <field name="x_icis_url" widget="url"/>
                    <field name="x_icis_ref_price"/>
                    <field name="x_icis_price_date"/>
                </group>
            </xpath>
        """,
    })
    print(f"  [OK] view created: {view_name}")
else:
    print(f"  [SKIP] view exists: {view_name}")

po_form = env.ref('purchase.purchase_order_form')
po_view_name = "Areks Demo - ICIS fields on PO lines"
# audit point 12: widget="monetary" bound to the line's own currency_id,
# so the ICIS price field itself visually shows it's in the PO's own
# currency (never a hidden/converted value) - consistent with price_unit
# right next to it.
po_view_arch = """
    <xpath expr="//field[@name='price_unit'][@readonly='qty_invoiced != 0']" position="after">
        <field name="x_icis_url" widget="url" string="ICIS"/>
        <field name="currency_id" invisible="1"/>
        <field name="x_icis_price" string="ICIS Fiyatı"
               widget="monetary" options="{'currency_field': 'currency_id'}"/>
        <field name="x_icis_variance_pct" string="Sapma %" readonly="1"/>
    </xpath>
"""
existing_po_view = View.search([('name', '=', po_view_name)], limit=1)
if not existing_po_view:
    View.create({
        'name': po_view_name,
        'model': 'purchase.order',
        'inherit_id': po_form.id,
        'arch_db': po_view_arch,
    })
    print(f"  [OK] view created: {po_view_name}")
elif existing_po_view.arch_db != po_view_arch:
    existing_po_view.arch_db = po_view_arch
    print(f"  [FIX] view corrected (monetary widget added): {po_view_name}")
else:
    print(f"  [SKIP] view exists: {po_view_name}")

env.cr.commit()

# -----------------------------------------------------------------------
# "ICIS Piyasa Fiyatları" menu -> act_url, opens in a new tab
# -----------------------------------------------------------------------
action_name = "ICIS Piyasa Fiyatları"
icis_action = Action.search([('name', '=', action_name)], limit=1)
if not icis_action:
    icis_action = Action.create({
        'name': action_name,
        'url': 'https://www.icis.com/explore/commodities/chemicals/polyurethanes/',
        'target': 'new',
    })
    print(f"  [OK] act_url action created: {action_name}")
else:
    print(f"  [SKIP] act_url action exists: {action_name}")

purchase_root = env.ref('purchase.menu_purchase_root')
if not Menu.search([('name', '=', action_name), ('parent_id', '=', purchase_root.id)], limit=1):
    Menu.create({
        'name': action_name,
        'parent_id': purchase_root.id,
        'action': f'ir.actions.act_url,{icis_action.id}',
        'sequence': 100,
    })
    print(f"  [OK] menu created under Purchase: {action_name}")
else:
    print(f"  [SKIP] menu exists under Purchase: {action_name}")

env.cr.commit()

print("=" * 70)
print("07a_icis_fields.py done")
print("=" * 70)
