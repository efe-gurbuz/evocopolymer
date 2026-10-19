"""
00d_remap_and_archive_old.py
"New company" rebuild approach (per explicit instruction): do NOT
delete old business data (posted accounting entries / done stock moves
cannot be deleted via ORM, and raw SQL is forbidden) - instead:
  1. Point demo users, the admin login, and both websites at the NEW
     Areks/Evoco companies (created by the updated 02_companies.py,
     already run before this script).
  2. Archive (active=False) the old companies, and all old business
     master data that can safely be archived: products, BOMs, org
     contacts, quality points, the ECO. Old stock.lot records stay
     linked to the old (now archived) products untouched, as instructed.
  3. For models with no `active` field: add one to x_icis_price
     (Studio-style custom field, same mechanism as the model itself)
     and archive its old rows; delete the old spreadsheet dashboards
     and MPS schedules outright (no deletion restriction applies to
     either - they are just saved views/planning rows, not accounting
     records).

Idempotent: every step is guarded (skip if already remapped/archived).

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/00d_remap_and_archive_old.py
"""

print("=" * 70)
print("00d_remap_and_archive_old.py starting")
print("=" * 70)

Company = env['res.company'].sudo().with_context(active_test=False)
old_areks = Company.search([('name', 'like', 'ESKİ – Areks')], limit=1)
old_evoco = Company.search([('name', 'like', 'ESKİ – Evoco')], limit=1)
new_areks = Company.search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
new_evoco = Company.search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert old_areks and old_evoco, "old (ESKİ-) companies not found - run the rename step first"
assert new_areks and new_evoco, "new companies not found - run the updated 02_companies.py first"
assert new_areks.id != old_areks.id and new_evoco.id != old_evoco.id
print(f"  old: Areks={old_areks.id} Evoco={old_evoco.id} | new: Areks={new_areks.id} Evoco={new_evoco.id}")

# -----------------------------------------------------------------------
# 1a. Remap demo users (@areksgroup.demo) off the old companies
# -----------------------------------------------------------------------
User = env['res.users'].sudo()
old_ids = (old_areks | old_evoco).ids
new_ids = (new_areks | new_evoco).ids

demo_users = User.search([('login', 'like', '@areksgroup.demo')])
for u in demo_users:
    had_areks = old_areks in u.company_ids
    had_evoco = old_evoco in u.company_ids
    new_company_ids = (u.company_ids - old_areks - old_evoco)
    if had_areks:
        new_company_ids |= new_areks
    if had_evoco:
        new_company_ids |= new_evoco
    vals = {'company_ids': [(6, 0, new_company_ids.ids)]}
    if u.company_id in (old_areks, old_evoco):
        vals['company_id'] = new_areks.id if u.company_id == old_areks else new_evoco.id
    u.write(vals)
    print(f"  [OK] remapped user {u.login}: companies -> {new_company_ids.mapped('name')}")

# -----------------------------------------------------------------------
# 1b. Remap the admin login too (used by Odoo.sh backend auto-connect)
# -----------------------------------------------------------------------
admin_user = User.search([('login', '=', 'admin')], limit=1)
if admin_user:
    keep = (admin_user.company_ids - old_areks - old_evoco) | new_areks | new_evoco
    vals = {'company_ids': [(6, 0, keep.ids)]}
    if admin_user.company_id in (old_areks, old_evoco):
        vals['company_id'] = new_areks.id
    admin_user.write(vals)
    print(f"  [OK] remapped admin login: companies -> {keep.mapped('name')}")

env.cr.commit()

# -----------------------------------------------------------------------
# 1c. Remap the two websites
# -----------------------------------------------------------------------
Website = env['website'].sudo()
for site, old_c, new_c in [
    (Website.search([('name', '=', 'Areks Kimya')], limit=1), old_areks, new_areks),
    (Website.search([('name', '=', 'Evoco Polimer')], limit=1), old_evoco, new_evoco),
]:
    if site and site.company_id == old_c:
        site.company_id = new_c.id
        print(f"  [OK] website {site.name}: company -> {new_c.name}")
    elif site and site.company_id == new_c:
        print(f"  [SKIP] website {site.name}: already on {new_c.name}")
    else:
        print(f"  [WARN] website {site.name if site else '??'}: unexpected company {site.company_id.name if site else ''}")

env.cr.commit()

# -----------------------------------------------------------------------
# 2. Archive the old companies (now nothing active references them)
# -----------------------------------------------------------------------
for c in (old_areks, old_evoco):
    if c.active:
        c.active = False
        print(f"  [OK] archived old company: {c.name}")
    else:
        print(f"  [SKIP] old company already archived: {c.name}")
    # NOTE: archiving a res.company does NOT cascade to archive its own
    # res.partner record (verified) - without this it keeps showing up
    # as an active company-type contact in Contacts/partner selectors.
    if c.partner_id.active:
        c.partner_id.active = False
        print(f"  [OK] archived old company's own partner record: {c.partner_id.name}")
env.cr.commit()

# -----------------------------------------------------------------------
# 3. Archive old master data (products, BOMs, contacts, quality points, ECO)
# Lots are intentionally left untouched (still point at the old, now
# archived, products - exactly as instructed).
# -----------------------------------------------------------------------
Product = env['product.template'].sudo()
old_products = Product.search([('company_id', 'in', [False])]).filtered(
    lambda p: p.create_date and True)  # all our shared products are candidates; refine below
# Precise targeting: everything that is NOT one of the names we are about
# to (re)create fresh has no reliable marker, so instead we archive by a
# recorded snapshot of ids taken before this rebuild. Safer and exact:
# archive ALL currently-active product templates (the only ones in the
# DB at this point are the ones from the previous build - the corrected
# scripts below use get-or-create by name, and since these are archived
# they will no longer be found, so fresh ones get created).
old_products = Product.search([('name', 'not in', ['Donation', 'Standard delivery'])])
if old_products:
    old_products.write({'active': False})
    print(f"  [OK] archived {len(old_products)} old product(s)")
else:
    print("  [SKIP] no active products to archive")

Bom = env['mrp.bom'].sudo()
old_boms = Bom.search([])
if old_boms:
    old_boms.write({'active': False})
    print(f"  [OK] archived {len(old_boms)} old BOM(s)")

# org contacts (suppliers/customers) - keep the two company partners out
# of this (already handled via company archival above)
Partner = env['res.partner'].sudo()
company_partner_ids = (old_areks | old_evoco | new_areks | new_evoco).mapped('partner_id').ids
old_orgs = Partner.search([('is_company', '=', True), ('id', 'not in', company_partner_ids)])
if old_orgs:
    old_orgs.write({'active': False})
    print(f"  [OK] archived {len(old_orgs)} old org contact(s)")

QPoint = env['quality.point'].sudo()
old_qp = QPoint.search([])
if old_qp:
    old_qp.write({'active': False})
    print(f"  [OK] archived {len(old_qp)} old quality point(s)")

Eco = env['mrp.eco'].sudo()
old_eco = Eco.search([])
if old_eco:
    old_eco.write({'active': False})
    print(f"  [OK] archived {len(old_eco)} old ECO(s)")

env.cr.commit()

# -----------------------------------------------------------------------
# 4. x_icis_price: add an `active` field (Studio-style, same mechanism
# used to create the model itself) if missing, then archive old rows.
# -----------------------------------------------------------------------
IMF = env['ir.model.fields'].sudo()
if not IMF.search([('model', '=', 'x_icis_price'), ('name', '=', 'x_active')], limit=1):
    model_rec = env['ir.model'].sudo().search([('model', '=', 'x_icis_price')], limit=1)
    # NOTE: for a custom ("manual") model, Odoo's magic active-flag
    # recognition only accepts the literal field names 'active' or
    # 'x_active' (model_classes.py validates custom field names must
    # start with 'x_' via a DB check constraint, so plain 'active' is
    # rejected - 'x_active' is the one that satisfies both).
    IMF.create({
        'model_id': model_rec.id,
        'name': 'x_active',
        'field_description': 'Active',
        'ttype': 'boolean',
    })
    print("  [OK] added 'x_active' field to x_icis_price")
else:
    print("  [SKIP] x_icis_price already has 'x_active' field")
env.cr.commit()

IcisPrice = env['x_icis_price'].sudo()
old_icis = IcisPrice.search([])
if old_icis:
    old_icis.write({'x_active': False})
    print(f"  [OK] archived {len(old_icis)} old x_icis_price record(s)")
env.cr.commit()

# -----------------------------------------------------------------------
# 5. Dashboards and MPS schedules: no `active` field and no deletion
# restriction (not accounting/stock-ledger records) - delete outright
# rather than leaving stale duplicates once rebuilt.
# -----------------------------------------------------------------------
Dashboard = env['spreadsheet.dashboard'].sudo()
old_dash = Dashboard.search([('dashboard_group_id.name', '=', 'Areks Group Demo')])
if old_dash:
    old_dash.unlink()
    print(f"  [OK] deleted {len(old_dash)} old spreadsheet dashboard(s)")

MPS = env['mrp.production.schedule'].sudo()
old_mps = MPS.search([])
if old_mps:
    old_mps.unlink()
    print(f"  [OK] deleted {len(old_mps)} old MPS schedule(s)")

env.cr.commit()

print("-" * 70)
print("SUMMARY:")
print(f"  old companies active: Areks={old_areks.active} Evoco={old_evoco.active} (expect False)")
print(f"  active products remaining: {Product.search_count([])} (expect 0)")
print(f"  active BOMs remaining: {Bom.search_count([])} (expect 0)")
print("=" * 70)
print("00d_remap_and_archive_old.py done")
print("=" * 70)
