"""
00_cleanup_demo.py
Remove standard Odoo `base` module demo content (demo users / demo partners)
before building the Areks Group demo database.

Idempotent: safe to run multiple times (uses explicit xmlid/res_id lookups,
`exists()` checks before acting).

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/00_cleanup_demo.py
"""

print("=" * 70)
print("00_cleanup_demo.py starting")
print("=" * 70)

Partner = env['res.partner'].sudo()
User = env['res.users'].sudo()
IMD = env['ir.model.data'].sudo()

# --- Users to remove (demo-only accounts; NOT the technical admin account) ---
user_xmlids = [
    ('base', 'user_demo'),          # Marc Demo
    ('base', 'demo_user0'),         # Joel Willis (demo portal user)
    ('base', 'user_light'),         # Monica Light
]

removed_users = []
kept_users_errors = []
for module, name in user_xmlids:
    rec = IMD.search([('module', '=', module), ('name', '=', name)], limit=1)
    if not rec or not rec.res_id:
        continue
    user = User.browse(rec.res_id)
    if not user.exists():
        continue
    label = f"{user.login} ({user.name})"
    try:
        with env.cr.savepoint():
            user.unlink()
        removed_users.append(label)
        print(f"  [OK] user removed: {label}")
    except Exception as e:
        kept_users_errors.append((label, str(e)))
        print(f"  [SKIP] could not remove user {label}: {e}")

# --- Attempt (best-effort) removal of the technical admin account's demo partner link ---
# We deliberately do NOT attempt to delete base.user_admin (Mitchell Admin, res.users id=2):
# it is the account referenced by create_uid/write_uid across virtually every base record
# and by the Odoo.sh auto-login mechanism. Deleting it is out of scope for a safe, idempotent
# cleanup script and was excluded on purpose.

# --- Demo commercial partners + their contacts/addresses ---
partner_xmlids = [
    ('base', 'res_partner_1'), ('base', 'res_partner_2'), ('base', 'res_partner_3'),
    ('base', 'res_partner_4'), ('base', 'res_partner_5'), ('base', 'res_partner_6'),
    ('base', 'res_partner_10'), ('base', 'res_partner_12'), ('base', 'res_partner_18'),
    ('base', 'res_partner_address_1'), ('base', 'res_partner_address_2'),
    ('base', 'res_partner_address_3'), ('base', 'res_partner_address_4'),
    ('base', 'res_partner_address_5'), ('base', 'res_partner_address_7'),
    ('base', 'res_partner_address_10'), ('base', 'res_partner_address_11'),
    ('base', 'res_partner_address_13'), ('base', 'res_partner_address_14'),
    ('base', 'res_partner_address_15'), ('base', 'res_partner_address_16'),
    ('base', 'res_partner_address_17'), ('base', 'res_partner_address_18'),
    ('base', 'res_partner_address_24'), ('base', 'res_partner_address_25'),
    ('base', 'res_partner_address_27'), ('base', 'res_partner_address_28'),
    ('base', 'res_partner_address_30'), ('base', 'res_partner_address_31'),
    ('base', 'res_partner_address_32'), ('base', 'res_partner_address_33'),
    ('base', 'res_partner_address_34'),
    ('base', 'res_partner_main1'), ('base', 'res_partner_main2'),
    # partners of the removed demo users (orphan partners left after user unlink)
    ('base', 'partner_demo'), ('base', 'partner_demo_portal'), ('base', 'partner_light'),
]

to_remove_ids = []
for module, name in partner_xmlids:
    rec = IMD.search([('module', '=', module), ('name', '=', name)], limit=1)
    if not rec or not rec.res_id:
        continue
    if Partner.browse(rec.res_id).exists():
        to_remove_ids.append(rec.res_id)

removed_partners = 0
partner_errors = []
if to_remove_ids:
    partners = Partner.browse(to_remove_ids)
    names = partners.mapped('name')
    try:
        with env.cr.savepoint():
            partners.unlink()
        removed_partners = len(to_remove_ids)
        print(f"  [OK] {removed_partners} demo partners removed: {names}")
    except Exception as e:
        partner_errors.append(str(e))
        print(f"  [SKIP] could not remove demo partners as a batch: {e}")
        # retry one by one so a single bad record doesn't block the rest
        for pid in to_remove_ids:
            p = Partner.browse(pid)
            if not p.exists():
                continue
            try:
                with env.cr.savepoint():
                    p.unlink()
                removed_partners += 1
                print(f"    [OK] removed partner {pid} ({p.name})")
            except Exception as e2:
                partner_errors.append(f"partner {pid} ({p.name}): {e2}")
                print(f"    [SKIP] partner {pid} ({p.name}): {e2}")

env.cr.commit()
print("=" * 70)
print(f"SUMMARY: users_removed={len(removed_users)} partners_removed={removed_partners}")
if kept_users_errors:
    print(f"USER ERRORS: {kept_users_errors}")
if partner_errors:
    print(f"PARTNER ERRORS: {partner_errors}")
print("00_cleanup_demo.py done")
print("=" * 70)
