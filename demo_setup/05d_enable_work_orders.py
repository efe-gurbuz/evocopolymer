"""
05d_enable_work_orders.py
Audit tur 4, point 1: enable Manufacturing > Settings > "Work Orders"
(mrp.group_mrp_routings) for both companies, so the implied group
reaches every internal user (needed for the BOM "Operations" tab /
Karışım Tankı work center set up in 05_boms.py to actually show up in
the UI for all demo users, not just via direct ORM access).

Idempotent: checks group membership before re-applying.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/05d_enable_work_orders.py
"""

print("=" * 70)
print("05d_enable_work_orders.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco

group = env.ref('mrp.group_mrp_routings')
internal_users = env['res.users'].sudo().search([('share', '=', False), ('active', '=', True)])
missing = internal_users - group.all_user_ids

if not missing:
    print(f"  [SKIP] Work Orders already enabled for all {len(internal_users)} internal users")
else:
    for company in (areks, evoco):
        settings = env['res.config.settings'].sudo().with_company(company).create({'group_mrp_routings': True})
        settings.execute()
        print(f"  [OK] Work Orders setting applied for {company.name}")
    env.cr.commit()

group = env.ref('mrp.group_mrp_routings')
print("-" * 70)
print(f"SUMMARY: mrp.group_mrp_routings members: {sorted(group.all_user_ids.mapped('login'))}")
print("=" * 70)
print("05d_enable_work_orders.py done")
print("=" * 70)
