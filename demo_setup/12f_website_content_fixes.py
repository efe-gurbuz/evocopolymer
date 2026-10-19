"""
12f_website_content_fixes.py
Audit tur 3, points 2-4: fixes to the GENERIC (shared, website_id=False)
website templates that both sites render by default - the contact
form's target model, the header phone number, and the footer content.

NOTE (bug found & fixed): a direct ir.ui.view.copy({'website_id': X,
...}) does NOT make a template become the "specific" version Odoo
resolves per-site - ir.ui.view.write() has its own Copy-On-Write (COW)
override (see website/models/ir_ui_view.py) that must be invoked by
writing to the GENERIC view WITH website_id in the context; that
override transparently creates/reuses the per-site copy under the same
key, re-parents the inherit tree, and (for page-routed templates like
website.contactus) also creates the matching website.page. Skipping
that mechanism (as an earlier pass here did via raw .copy()) silently
left the specific copy unresolved - the live site kept rendering the
GENERIC content (verified over real HTTP: /contactus still served
data-model_name="mail.mail", and the header rendered BOTH the generic
placeholder phone AND the new one side by side instead of replacing
it).

Idempotent: cow_write() always targets the (possibly already-COW'd)
specific view for that site (ir.ui.view.write()'s own override
reuses it if found), so re-running just re-applies the same content.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12f_website_content_fixes.py
"""

print("=" * 70)
print("12f_website_content_fixes.py starting")
print("=" * 70)

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
areks_site = env['website'].sudo().search([('company_id', '=', areks.id)], limit=1)
evoco_site = env['website'].sudo().search([('company_id', '=', evoco.id)], limit=1)
V = env['ir.ui.view'].sudo()

ABOUT = {
    areks.id: ("Areks Kimya, otomotiv ve sanayi sektörüne poliüretan hammaddesi "
               "(poliol, izosiyanat, katalist, silikon ve yanmazlık katkıları) tedarik eden bir "
               "kimyasal dağıtım şirketidir."
               "<br/><br/>Müşterilerimize güvenilir tedarik, teknik destek ve rekabetçi fiyatlarla hizmet veriyoruz."),
    evoco.id: ("Evoco Polimer, Ar-Ge odaklı poliüretan sistemleri (rijit panel, sprey izolasyon, "
               "soğutma, mobilya/yatak ve CASE elastomer uygulamaları) geliştiren ve üreten bir "
               "polimer teknolojisi şirketidir."
               "<br/><br/>İnovasyonu ve müşteri ihtiyaçlarına özel çözümleri önceliğimiz olarak görüyoruz."),
}
HEADINGS_TR = {
    'Useful Links': 'Faydalı Bağlantılar',
    'About us': 'Hakkımızda',
    'Connect with us': 'Bize Ulaşın',
    'Contact us': 'İletişim',
}


def cow_write(generic_view, site, new_arch):
    specific_before = V.search([('key', '=', generic_view.key), ('website_id', '=', site.id)], limit=1)
    if specific_before and specific_before.arch_db == new_arch:
        print(f"    [SKIP] {site.name}: specific view already up to date (id={specific_before.id})")
        return specific_before
    generic_view.with_context(website_id=site.id).write({'arch_db': new_arch})
    specific = V.search([('key', '=', generic_view.key), ('website_id', '=', site.id)], limit=1)
    print(f"    [OK] {site.name}: specific view {'updated' if specific_before else 'created'} (id={specific.id})")
    return specific


# -----------------------------------------------------------------------
# 1. /contactus -> crm.lead (audit tur 3, point 2)
# -----------------------------------------------------------------------
contactus_generic = V.search([('key', '=', 'website.contactus'), ('website_id', '=', False)], limit=1)
assert contactus_generic, "generic website.contactus view not found"
crm_arch = contactus_generic.arch_db
crm_arch = crm_arch.replace('data-model_name="mail.mail"', 'data-model_name="crm.lead"')
crm_arch = crm_arch.replace('name="name" required="" data-fill-with="name"',
                            'name="contact_name" required="" data-fill-with="name"')
crm_arch = crm_arch.replace('name="company" data-fill-with="parent_name"',
                            'name="partner_name" data-fill-with="parent_name"')
crm_arch = crm_arch.replace('name="subject" required=""', 'name="name" required=""')
assert 'mail.mail' not in crm_arch and 'data-model_name="crm.lead"' in crm_arch

print("--- /contactus -> crm.lead ---")
for site in (areks_site, evoco_site):
    cow_write(contactus_generic, site, crm_arch)
env.cr.commit()

# -----------------------------------------------------------------------
# 2. Header phone (audit tur 3, point 3)
# -----------------------------------------------------------------------
header_generic = V.search([('key', '=', 'website.header_text_element'), ('website_id', '=', False)], limit=1)
assert header_generic, "generic website.header_text_element view not found"

print("--- Header phone ---")
for site, company in ((areks_site, areks), (evoco_site, evoco)):
    new_arch = header_generic.arch_db.replace('+1 555-555-5556', company.phone)
    cow_write(header_generic, site, new_arch)
env.cr.commit()

# -----------------------------------------------------------------------
# 3. Footer: real contact info, Turkish headings (audit tur 3, point 4)
# -----------------------------------------------------------------------
footer_generic = V.search([('key', '=', 'website.footer_custom'), ('website_id', '=', False)], limit=1)
assert footer_generic, "generic website.footer_custom view not found"

print("--- Footer ---")
for site, company in ((areks_site, areks), (evoco_site, evoco)):
    new_arch = footer_generic.arch_db
    new_arch = new_arch.replace(
        "We are a team of passionate people whose goal is to improve everyone's life through "
        "disruptive products. We build great products to solve your business problems.\n"
        "                            <br/><br/>Our products are designed for small to medium size "
        "companies willing to optimize their performance.",
        ABOUT[company.id])
    new_arch = new_arch.replace("mailto:info@yourcompany.example.com", f"mailto:{company.email}")
    new_arch = new_arch.replace(">info@yourcompany.example.com<", f">{company.email}<")
    new_arch = new_arch.replace('tel:+1 555-555-5556', f"tel:{company.phone}")
    new_arch = new_arch.replace(">+1 555-555-5556<", f">{company.phone}<")
    for en, tr in HEADINGS_TR.items():
        new_arch = new_arch.replace(f">{en}<", f">{tr}<")
    cow_write(footer_generic, site, new_arch)
env.cr.commit()

# -----------------------------------------------------------------------
# 4. Homepage / "Hakkımızda" page: Areks was founded in 2007, not 1998
#    (audit tur 3, point 4) - these are Areks's OWN site-specific pages
#    already (not generic COW templates), so a direct in-place edit is
#    correct here (no COW mechanism needed).
# -----------------------------------------------------------------------
print("--- Founding year (Areks homepage + Hakkımızda) ---")
for v in V.search([('arch_db', 'like', "1998'den Beri"), ('website_id', '=', areks_site.id)]):
    v.arch_db = v.arch_db.replace("1998'den Beri", "2007'den Beri")
    print(f"    [OK] fixed founding-year claim in view id={v.id} ({v.name})")
env.cr.commit()

print("=" * 70)
print("12f_website_content_fixes.py done")
print("=" * 70)
