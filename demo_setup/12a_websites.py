"""
12a_websites.py
Two websites, one per company:
  - "Areks Kimya" (reuses the default "My Website", already linked to
    Areks) - languages TR (default)/EN/AR.
  - "Evoco Polimer" (new) - languages TR (default)/EN.
Both: B2B mode (prevent_sale on zero-price products -> "Contact Us"
instead of Add to Cart, per the website's own standard mechanism),
menus, and a dedicated per-company CRM team wired as the site's
default lead destination for the contact/quote forms.

Idempotent: search by name before create throughout.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12a_websites.py
"""

print("=" * 70)
print("12a_websites.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
Website = env['website'].sudo()
Lang = env['res.lang'].sudo().with_context(active_test=False)
Menu = env['website.menu'].sudo()
Team = env['crm.team'].sudo()
Partner = env['res.partner'].sudo()

# --- Languages ---
for code in ('en_US', 'tr_TR', 'ar_001'):
    lang = Lang.search([('code', '=', code)], limit=1)
    if not lang.active:
        env['res.lang']._activate_lang(code)
        print(f"  [OK] activated language {code}")
    else:
        print(f"  [SKIP] language {code} already active")
env.cr.commit()

tr = Lang.search([('code', '=', 'tr_TR')], limit=1)
en = Lang.search([('code', '=', 'en_US')], limit=1)
ar = Lang.search([('code', '=', 'ar_001')], limit=1)

# --- CRM teams per company ---
aristotle = Partner.search([('email', '=', 'aristotle@areksgroup.demo')], limit=1)
nietzsche = Partner.search([('email', '=', 'nietzsche@areksgroup.demo')], limit=1)
aristotle_user = env['res.users'].sudo().search([('login', '=', 'aristotle@areksgroup.demo')], limit=1)
nietzsche_user = env['res.users'].sudo().search([('login', '=', 'nietzsche@areksgroup.demo')], limit=1)


def get_or_create_team(name, company, leader_user):
    # audit-rebuild fix: a name-only match can hit the leftover team
    # still scoped to the OLD (now archived/renamed) company.
    team = Team.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if team:
        print(f"  [SKIP] CRM team exists: {name}")
        return team
    team = Team.create({
        'name': name,
        'company_id': company.id,
        'user_id': leader_user.id if leader_user else False,
        'member_ids': [(4, leader_user.id)] if leader_user else [],
    })
    print(f"  [OK] CRM team created: {name}")
    return team


areks_team = get_or_create_team("Areks Satış Ekibi", areks, aristotle_user)
evoco_team = get_or_create_team("Evoco Satış Ekibi", evoco, nietzsche_user)
env.cr.commit()

# -----------------------------------------------------------------------
# Areks Kimya website (reuse default "My Website")
# -----------------------------------------------------------------------
areks_site = Website.search([('company_id', '=', areks.id)], limit=1)
if not areks_site:
    areks_site = Website.search([], limit=1)  # fall back to the default one
areks_site.write({
    'name': 'Areks Kimya',
    'company_id': areks.id,
    'language_ids': [(6, 0, [tr.id, en.id, ar.id])],
    'default_lang_id': tr.id,
    'prevent_sale': True,
    'prevent_sale_for': 'zero_price',
    'crm_default_team_id': areks_team.id,
})
print(f"  [OK] Areks Kimya website configured (id={areks_site.id})")

# -----------------------------------------------------------------------
# Evoco Polimer website (new)
# -----------------------------------------------------------------------
evoco_site = Website.search([('name', '=', 'Evoco Polimer')], limit=1)
if not evoco_site:
    evoco_site = Website.create({
        'name': 'Evoco Polimer',
        'company_id': evoco.id,
        'language_ids': [(6, 0, [tr.id, en.id])],
        'default_lang_id': tr.id,
        'prevent_sale': True,
        'prevent_sale_for': 'zero_price',
        'crm_default_team_id': evoco_team.id,
    })
    print(f"  [OK] Evoco Polimer website created (id={evoco_site.id})")
else:
    evoco_site.write({
        'company_id': evoco.id,
        'language_ids': [(6, 0, [tr.id, en.id])],
        'default_lang_id': tr.id,
        'prevent_sale': True,
        'prevent_sale_for': 'zero_price',
        'crm_default_team_id': evoco_team.id,
    })
    print(f"  [SKIP->updated] Evoco Polimer website already existed (id={evoco_site.id})")

env.cr.commit()

# -----------------------------------------------------------------------
# Menus
# -----------------------------------------------------------------------
def get_or_create_menu(name, website, url, parent=None, sequence=10):
    domain = [('name', '=', name), ('website_id', '=', website.id)]
    if parent:
        domain.append(('parent_id', '=', parent.id))
    existing = Menu.search(domain, limit=1)
    if existing:
        print(f"    [SKIP] menu exists: {website.name} / {name}")
        return existing
    vals = {
        'name': name, 'url': url, 'website_id': website.id,
        'sequence': sequence,
        'parent_id': parent.id if parent else website.menu_id.id,
    }
    m = Menu.create(vals)
    print(f"    [OK] menu created: {website.name} / {name}")
    return m


# NOTE: only the baseline items common to every later redesign pass are
# listed here (Ana Sayfa first, per instructions) - "Ürünler"/"Kalite
# Politikası" (Areks) and "Çözümler"/"Ar-Ge Hizmetleri" (Evoco) are
# deliberately NOT listed here any more: 12d/12e_*.py build a richer
# dropdown structure for those exact topics ("Ürünlerimiz"/"Kurumsal"
# resp. "Hizmetler"/"Araştırma Alanları") - keeping the old flat names
# here created duplicate top-level menu items alongside the real ones.
AREKS_MENUS = [
    ("Ana Sayfa", "/"),
    ("Hakkımızda", "/hakkimizda"),
    ("İletişim", "/contactus"),
    ("Teklif İste", "/teklif-al"),  # audit point 10: button/menu text must read "Teklif İste"
]
for name, url in AREKS_MENUS:
    get_or_create_menu(name, areks_site, url)

EVOCO_MENUS = [
    ("Ana Sayfa", "/"),
    ("Hakkımızda", "/hakkimizda"),
    ("İletişim", "/contactus"),
    ("Teklif İste", "/teklif-al"),
]
for name, url in EVOCO_MENUS:
    get_or_create_menu(name, evoco_site, url)

# --- Remove the auto-generated default English menu items ("Home",
# "Shop") that duplicate our own Turkish menu entries on each site ---
for site in (areks_site, evoco_site):
    dupes = Menu.search([
        ('website_id', '=', site.id),
        ('name', 'in', ['Home', 'Shop']),
    ])
    if dupes:
        print(f"  [OK] removing {len(dupes)} duplicate default menu item(s) on {site.name}: {dupes.mapped('name')}")
        dupes.unlink()

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: Areks site id={areks_site.id} langs={areks_site.language_ids.mapped('code')}")
print(f"SUMMARY: Evoco site id={evoco_site.id} langs={evoco_site.language_ids.mapped('code')}")
print("=" * 70)
print("12a_websites.py done")
print("=" * 70)
