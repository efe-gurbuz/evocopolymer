"""
12b_catalog.py
Website catalog: B2B zero-price pricelist per site (drives the
"Contact Us" / no-cart behaviour via website.prevent_sale +
prevent_sale_for='zero_price', configured in 12a), public categories,
and product -> website / category assignment.

- Areks site: Polioller, İzosiyanatlar, Yardımcı Kimyasallar (exclusive
  to Areks), Polyol Sistemleri (Evoco's PU systems, shown here too).
- Evoco site: İnşaat & Yalıtım, Soğutma, Mobilya & Yatak, Ses Yalıtımı,
  CASE (application-based), covering Evoco's finished PU systems.
- The PU system finished products (EVO-RP 210 etc.) get website_id=False
  so they are visible regardless of which site is being browsed, per
  "Polyol sistemleri her iki sitede görünsün".
- Evoco's internal WIP (EVO-PE 35, EVO-PMX R) stay unpublished.

Idempotent: search by name before create; product writes are safe to
repeat.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12b_catalog.py
"""

print("=" * 70)
print("12b_catalog.py starting")
print("=" * 70)

Website = env['website'].sudo()
Product = env['product.template'].sudo()
PublicCategory = env['product.public.category'].sudo()
Pricelist = env['product.pricelist'].sudo()
TRY = env['res.currency'].sudo().search([('name', '=', 'TRY')], limit=1)

areks_site = Website.search([('name', '=', 'Areks Kimya')], limit=1)
evoco_site = Website.search([('name', '=', 'Evoco Polimer')], limit=1)
areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)

# -----------------------------------------------------------------------
# B2B zero-price pricelists (one per website/company)
# -----------------------------------------------------------------------
def get_or_create_zero_pricelist(name, company, site):
    pl = Pricelist.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not pl:
        pl = Pricelist.create({
            'name': name,
            'company_id': company.id,
            'currency_id': TRY.id,
            'item_ids': [(0, 0, {
                'applied_on': '3_global',
                'compute_price': 'fixed',
                'fixed_price': 0.0,
            })],
        })
        print(f"  [OK] B2B zero-price pricelist created: {name}")
    else:
        print(f"  [SKIP] B2B zero-price pricelist exists: {name}")
    if site.pricelist_id != pl or pl not in site.pricelist_ids:
        site.write({'pricelist_id': pl.id, 'pricelist_ids': [(4, pl.id)]})
    return pl


get_or_create_zero_pricelist("B2B - Fiyat Gizli (Areks)", areks, areks_site)
get_or_create_zero_pricelist("B2B - Fiyat Gizli (Evoco)", evoco, evoco_site)
env.cr.commit()

# -----------------------------------------------------------------------
# Public categories
# -----------------------------------------------------------------------
def get_or_create_pcat(name, site):
    cat = PublicCategory.search([('name', '=', name), ('website_id', '=', site.id)], limit=1)
    if cat:
        print(f"  [SKIP] public category exists: {site.name} / {name}")
        return cat
    cat = PublicCategory.create({'name': name, 'website_id': site.id})
    print(f"  [OK] public category created: {site.name} / {name}")
    return cat


cat_polioller = get_or_create_pcat("Polioller", areks_site)
cat_izosiyanat = get_or_create_pcat("İzosiyanatlar", areks_site)
cat_yardimci = get_or_create_pcat("Yardımcı Kimyasallar", areks_site)
cat_polyol_sistem = get_or_create_pcat("Polyol Sistemleri", areks_site)

cat_insaat = get_or_create_pcat("İnşaat & Yalıtım", evoco_site)
cat_sogutma = get_or_create_pcat("Soğutma", evoco_site)
cat_mobilya = get_or_create_pcat("Mobilya & Yatak", evoco_site)
cat_ses = get_or_create_pcat("Ses Yalıtımı", evoco_site)
cat_case = get_or_create_pcat("CASE", evoco_site)

env.cr.commit()

# -----------------------------------------------------------------------
# Product -> website + public category assignment
# -----------------------------------------------------------------------
def publish(product_name, website, categories, by_code=False):
    domain = [('default_code', '=', product_name)] if by_code else [('name', '=', product_name)]
    prod = Product.search(domain, limit=1)
    assert prod, f"product not found: {product_name}"
    prod.write({
        'website_id': website.id if website else False,
        'website_published': True,
        'public_categ_ids': [(6, 0, [c.id for c in categories])],
    })
    print(f"  [OK] published: {prod.name} -> site={website.name if website else 'ALL'} "
          f"categories={[c.name for c in categories]}")


hammadde_map = [
    (["Konvansiyonel Şeffaf Polyol", "%15 Polimerik Polyol (POP)", "%25 Polimerik Polyol (POP)",
      "%40 Polimerik Polyol (POP)", "R4110", "Semi-Rigid Poliol", "Poliester Poliol 35 OH 4500mw",
      "Poliester Poliol C220 - LE220A"], cat_polioller),
    (["TDI", "Polimerik MDI", "Monomerik MDI", "Modifiye MDI"], cat_izosiyanat),
    (["Cyclopentane", "N-Pentane", "Metylal (Pure) 05050", "365MFC", "245FA",
      "Flexible Slabstock Katalist", "Rigid Grup Katalist", "Flexible Slabstock Silikon",
      "Rigid Grup Silikon", "Yanmazlık TCPP", "Yanmazlık TEP", "Kalıp Ayırıcı Sintaliz 6006",
      "Renk Pastası", "Adipik Asit", "Dietilen Glikol (DEG)"], cat_yardimci),
]
for names, categ in hammadde_map:
    for name in names:
        publish(name, areks_site, [categ])

# PU system finished products: visible on BOTH sites (website_id=False),
# tagged into Areks's "Polyol Sistemleri" AND Evoco's application categories
PU_SYSTEMS = [
    ("EVO-RP 210", [cat_polyol_sistem, cat_insaat]),
    ("EVO-RS 320", [cat_polyol_sistem, cat_insaat]),
    ("EVO-RC 150", [cat_polyol_sistem, cat_sogutma]),
    ("EVO-FS 400", [cat_polyol_sistem, cat_mobilya]),
    ("EVO-SR 500", [cat_polyol_sistem, cat_ses]),
    ("EVO-CE 600", [cat_polyol_sistem, cat_case]),
    ("EVO-RP 210 SET", [cat_polyol_sistem, cat_insaat]),
]
for code, categs in PU_SYSTEMS:
    publish(code, None, categs, by_code=True)

# internal WIP: keep unpublished
for code in ("EVO-PE 35", "EVO-PMX R"):
    prod = Product.search([('default_code', '=', code)], limit=1)
    if prod.website_published:
        prod.website_published = False
    print(f"  [INFO] kept unpublished (internal WIP): {prod.name}")

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: published products = "
      f"{Product.search_count([('website_published', '=', True)])}")
print("=" * 70)
print("12b_catalog.py done")
print("=" * 70)
