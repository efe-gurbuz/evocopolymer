"""
09_users.py
Areks Group demo users (login=<firstname>@areksgroup.demo,
password=demo123), scoped to the right company/companies and groups.

Idempotent: search by login before create.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/09_users.py
"""

print("=" * 70)
print("09_users.py starting")
print("=" * 70)

User = env['res.users'].sudo()
Group = env['res.groups'].sudo()
areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)

G_SYSTEM = env.ref('base.group_system')
G_PURCHASE_MANAGER = env.ref('purchase.group_purchase_manager')
G_PURCHASE_USER = env.ref('purchase.group_purchase_user')
G_ACCOUNT_MANAGER = env.ref('account.group_account_manager')
G_SALE_MANAGER = env.ref('sales_team.group_sale_manager')
G_MRP_MANAGER = env.ref('mrp.group_mrp_manager')
G_QUALITY_MANAGER = env.ref('quality.group_quality_manager')
G_STOCK_MANAGER = env.ref('stock.group_stock_manager')
G_PLM_MANAGER = env.ref('mrp_plm.group_plm_manager')
G_WEBSITE_DESIGNER = env.ref('website.group_website_designer')

# audit point 8: Çağlar & İlhan = "admin in every app", both companies -
# the full set of per-app Administrator/Manager groups actually used in
# this demo (not just Settings/base.group_system).
ALL_APPS_ADMIN = [
    G_SYSTEM, G_STOCK_MANAGER, G_PURCHASE_MANAGER, G_SALE_MANAGER,
    G_MRP_MANAGER, G_QUALITY_MANAGER, G_ACCOUNT_MANAGER, G_PLM_MANAGER,
    G_WEBSITE_DESIGNER,
]

USERS = [
    # firstname, role (for the chatter/job title), companies, extra groups
    ("Çağlar", "Genel Müdür", [areks, evoco], ALL_APPS_ADMIN),
    ("İlhan", "Group CTO", [areks, evoco], ALL_APPS_ADMIN),
    ("Aysen", "Satınalma Müdürü", [areks, evoco], [G_PURCHASE_MANAGER]),
    ("Candan", "Muhasebe & Finans Müdürü", [areks, evoco], [G_ACCOUNT_MANAGER]),
    ("Aristotle", "Areks Satış Müdürü", [areks], [G_SALE_MANAGER]),
    ("Nietzsche", "Evoco Satış Müdürü", [evoco], [G_SALE_MANAGER]),
    # audit point 8: Eser = PLM manager specifically (not just MRP/Quality)
    ("Eser", "Ar-Ge Müdürü", [evoco], [G_MRP_MANAGER, G_QUALITY_MANAGER, G_PLM_MANAGER]),
    ("Hegel", "Üretim & Planlama Müdürü", [evoco], [G_MRP_MANAGER]),
    # audit point 8: NEW - Marx, purchase USER only (no manager group),
    # both companies - must land in "to approve" above the threshold.
    ("Marx", "Satınalma Uzmanı", [areks, evoco], [G_PURCHASE_USER]),
]

created = []
updated = []
translit = {
    'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
    'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U',
}
for firstname, role, companies, groups in USERS:
    ascii_first = ''.join(translit.get(c, c) for c in firstname)
    login = f"{ascii_first.lower()}@areksgroup.demo"

    default_company = companies[0]
    existing = User.search([('login', '=', login)], limit=1)
    if existing:
        # self-healing: make sure company access + required groups are
        # correct even if this user was created by an earlier run, before
        # some of the audit-point-8 requirements existed.
        fix_vals = {}
        want_company_ids = set(c.id for c in companies)
        have_company_ids = set(existing.company_ids.ids)
        if not want_company_ids.issubset(have_company_ids):
            fix_vals['company_ids'] = [(4, c.id) for c in companies]
        if existing.company_id.id not in want_company_ids:
            fix_vals['company_id'] = default_company.id
        missing_groups = [g for g in groups if g not in existing.group_ids]
        if missing_groups:
            fix_vals['group_ids'] = [(4, g.id) for g in missing_groups]
        if fix_vals:
            existing.write(fix_vals)
            updated.append(firstname)
            print(f"  [FIX] user updated: {firstname} ({login}) -> {list(fix_vals.keys())}")
        else:
            print(f"  [SKIP] user exists, already correct: {firstname} ({login})")
        continue

    vals = {
        'name': f"{firstname} ({role})",
        'login': login,
        'email': login,
        'password': 'demo123',
        'company_id': default_company.id,
        'company_ids': [(6, 0, [c.id for c in companies])],
        'group_ids': [(4, g.id) for g in groups],
        'lang': 'tr_TR',
    }
    user = User.create(vals)
    created.append(firstname)
    print(f"  [OK] user created: {firstname} ({role}) login={login} companies={[c.name for c in companies]}")

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: created={len(created)} ({created}) updated={len(updated)} ({updated})")
print(f"  total Areks Group demo users: {User.search_count([('login', 'like', '@areksgroup.demo')])}")
print("=" * 70)
print("09_users.py done")
print("=" * 70)
