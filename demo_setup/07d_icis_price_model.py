"""
07d_icis_price_model.py
ICIS PLAN B: a manual (Studio-style) model `x_icis_price` for entering
ICIS reference prices by hand (product, date, price, currency), with
list/form views and a menu under Purchase > Configuration.

Idempotent: search-before-create for model/fields/views/menu.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/07d_icis_price_model.py
"""

print("=" * 70)
print("07d_icis_price_model.py starting")
print("=" * 70)

IModel = env['ir.model'].sudo()
IMF = env['ir.model.fields'].sudo()
View = env['ir.ui.view'].sudo()
Menu = env['ir.ui.menu'].sudo()
WindowAction = env['ir.actions.act_window'].sudo()

MODEL_NAME = 'x_icis_price'

model = IModel.search([('model', '=', MODEL_NAME)], limit=1)
if not model:
    model = IModel.create({
        'name': 'ICIS Fiyat Girişi',
        'model': MODEL_NAME,
        'field_id': [
            (0, 0, {'name': 'x_name', 'field_description': 'Açıklama', 'ttype': 'char'}),
            (0, 0, {'name': 'x_product_id', 'field_description': 'Ürün',
                     'ttype': 'many2one', 'relation': 'product.template', 'required': True,
                     'on_delete': 'cascade'}),
            (0, 0, {'name': 'x_date', 'field_description': 'Tarih', 'ttype': 'date', 'required': True}),
            (0, 0, {'name': 'x_price', 'field_description': 'Fiyat', 'ttype': 'float'}),
            (0, 0, {'name': 'x_currency_id', 'field_description': 'Para Birimi',
                     'ttype': 'many2one', 'relation': 'res.currency'}),
        ],
    })
    print(f"  [OK] model created: {MODEL_NAME} (id={model.id})")
else:
    print(f"  [SKIP] model exists: {MODEL_NAME} (id={model.id})")

env.cr.commit()

ModelObj = env[MODEL_NAME].sudo()

# --- Views ---
list_view_name = "x_icis_price.list"
list_view = View.search([('name', '=', list_view_name)], limit=1)
if not list_view:
    list_view = View.create({
        'name': list_view_name,
        'model': MODEL_NAME,
        'type': 'list',
        'arch_db': """
            <list string="ICIS Fiyat Girişleri">
                <field name="x_product_id"/>
                <field name="x_date"/>
                <field name="x_price"/>
                <field name="x_currency_id"/>
            </list>
        """,
    })
    print(f"  [OK] list view created (id={list_view.id})")
else:
    print(f"  [SKIP] list view exists (id={list_view.id})")

form_view_name = "x_icis_price.form"
form_view = View.search([('name', '=', form_view_name)], limit=1)
if not form_view:
    form_view = View.create({
        'name': form_view_name,
        'model': MODEL_NAME,
        'type': 'form',
        'arch_db': """
            <form string="ICIS Fiyat Girişi">
                <sheet>
                    <group>
                        <field name="x_product_id"/>
                        <field name="x_date"/>
                        <field name="x_price"/>
                        <field name="x_currency_id"/>
                        <field name="x_name"/>
                    </group>
                </sheet>
            </form>
        """,
    })
    print(f"  [OK] form view created (id={form_view.id})")
else:
    print(f"  [SKIP] form view exists (id={form_view.id})")

env.cr.commit()

# --- Window action + menu under Purchase > Configuration ---
action_name = "ICIS Fiyat Girişleri"
action = WindowAction.search([('name', '=', action_name), ('res_model', '=', MODEL_NAME)], limit=1)
if not action:
    action = WindowAction.create({
        'name': action_name,
        'res_model': MODEL_NAME,
        'view_mode': 'list,form',
    })
    print(f"  [OK] window action created (id={action.id})")
else:
    print(f"  [SKIP] window action exists (id={action.id})")

purchase_config = env.ref('purchase.menu_purchase_config')
if not Menu.search([('name', '=', action_name), ('parent_id', '=', purchase_config.id)], limit=1):
    Menu.create({
        'name': action_name,
        'parent_id': purchase_config.id,
        'action': f'ir.actions.act_window,{action.id}',
        'sequence': 100,
    })
    print(f"  [OK] menu created under Purchase > Configuration: {action_name}")
else:
    print(f"  [SKIP] menu exists under Purchase > Configuration: {action_name}")

env.cr.commit()

print("=" * 70)
print("07d_icis_price_model.py done")
print("=" * 70)
