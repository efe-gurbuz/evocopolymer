"""
12d_reference_redesign.py
Align the two websites with the real reference sites the user shared
(arekskimya.com, evocopolymers.com): matching nav structure (incl.
dropdowns), real page content for each nav target (the original menu
items from 12a pointed at URLs with NO underlying page - 404s; fixed
here), blogs, and the real brand accent colors/hero copy style.

Idempotent: search-before-create for pages/menus/blogs; hero color
replace is done via a marker-guarded string substitution.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12d_reference_redesign.py
"""

print("=" * 70)
print("12d_reference_redesign.py starting")
print("=" * 70)

Website = env['website'].sudo()
Menu = env['website.menu'].sudo()
Page = env['website.page'].sudo()
Blog = env['blog.blog'].sudo()
PublicCategory = env['product.public.category'].sudo()

areks_site = Website.search([('name', '=', 'Areks Kimya')], limit=1)
evoco_site = Website.search([('name', '=', 'Evoco Polimer')], limit=1)


def get_or_create_page(site, url, title, html_body):
    existing = Page.search([('url', '=', url), ('website_id', '=', site.id)], limit=1)
    if existing:
        print(f"  [SKIP] page exists: {site.name}{url}")
        return existing
    # NOTE (found & fixed): new_page() scopes itself via self.env.website
    # (the *context* current website), NOT the recordset it's called on -
    # calling `site.new_page(...)` directly silently created
    # website_id=False pages (invisible to this site-scoped search, so
    # every re-run created yet another duplicate). with_context fixes it.
    res = site.with_context(website_id=site.id).new_page(
        name=title, add_menu=False, page_title=title)
    page = Page.browse(res['page_id'])
    assert page.website_id == site, f"new_page still not scoped to {site.name}"
    # route it to our intended url (new_page slugifies the name into one)
    page.url = url
    # NOTE: new_page() creates the page UNPUBLISHED by default (404 for
    # anonymous visitors until published) - found via a live curl check.
    page.is_published = True
    view = env['ir.ui.view'].sudo().browse(res['view_id'])
    view.arch_db = view.arch_db.replace(
        '<div id="wrap" class="oe_structure oe_empty"/>',
        f'<div id="wrap" class="oe_structure">{html_body}</div>',
    )
    print(f"  [OK] page created: {site.name}{url}")
    return page


def get_or_create_blog(site, name):
    b = Blog.search([('name', '=', name), ('website_id', '=', site.id)], limit=1)
    if b:
        print(f"  [SKIP] blog exists: {site.name} / {name}")
        return b
    b = Blog.create({'name': name, 'website_id': site.id})
    print(f"  [OK] blog created: {site.name} / {name}")
    return b


def cat_url(name, site):
    c = PublicCategory.search([('name', '=', name), ('website_id', '=', site.id)], limit=1)
    return c.website_url if c else '/shop'


# -----------------------------------------------------------------------
# Content pages (fix the 404s + align with reference structure)
# -----------------------------------------------------------------------
get_or_create_page(areks_site, "/hakkimizda", "Hakkımızda", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Hakkımızda</h1>
<p>Areks Kimya Otomotiv San. ve Dış Tic. A.Ş., poliuretan endüstrisine
yönelik hammadde tedarikinde 19 yılı aşan deneyimiyle, poliol,
izosiyanat ve yardımcı kimyasal gruplarında sanayiye kesintisiz ve
güvenilir tedarik sağlar.</p>
<h3>Neden Biz?</h3>
<ul>
<li>Rekabetçi fiyat</li>
<li>Sürekli teknik destek</li>
<li>Zamanında teslimat</li>
<li>Kalite anlayışı</li>
</ul>
</div></section>
""")

get_or_create_page(areks_site, "/misyon-vizyon", "Misyon &amp; Vizyon", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Misyon &amp; Vizyon</h1>
<p><b>Misyonumuz:</b> Poliuretan üreticilerine, geniş ürün portföyümüz
ve teknik bilgi birikimimizle yüksek performanslı, güvenilir çözümler
sunmak.</p>
<p><b>Vizyonumuz:</b> Türkiye ve çevre bölgede poliuretan hammadde
tedarikinde ilk tercih edilen güvenilir iş ortağı olmak.</p>
</div></section>
""")

get_or_create_page(areks_site, "/kalite-politikasi", "Kalite Politikamız", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Kalite Politikamız</h1>
<p>Areks Kimya olarak; ürün kalitesinden ödün vermeden, sürdürülebilir
tedarik zinciri yönetimi ve sürekli iyileştirme ilkesiyle çalışırız.
Tüm hammaddelerimiz, uluslararası kalite standartlarına uygun
tedarikçilerden temin edilir ve parti bazında izlenebilirlik
sağlanır.</p>
</div></section>
""")

get_or_create_page(areks_site, "/teklif-al", "Teklif İste", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Teklif İste</h1>
<p>İhtiyacınız olan hammadde ve miktarı belirtin, satış ekibimiz en
kısa sürede sizinle iletişime geçsin.</p>
<a href="/contactus" class="btn btn-primary">İletişim Formuna Git</a>
</div></section>
""")

get_or_create_page(evoco_site, "/hakkimizda", "Hakkımızda", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Hakkımızda</h1>
<p>Evoco Polimer San. Tic. A.Ş., Gebze/Kocaeli'deki Ar-Ge laboratuvarı
ve üretim tesisinde poliüretan, poliester poliol, reçine ve kompozit
malzeme alanlarında özel formülasyonlar geliştirir.</p>
</div></section>
""")

get_or_create_page(evoco_site, "/arastirma-alanlari", "Araştırma Alanları", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Araştırma Alanları</h1>
<div id="poliuretan"><h3>Poliüretan</h3><p>Rijit, esnek ve semi-rigid
poliüretan sistemleri için formülasyon geliştirme.</p></div>
<div id="poliester-polioller"><h3>Poliester Polioller</h3>
<p>CASE ve özel uygulamalar için poliester esaslı poliol üretimi.</p></div>
<div id="recineler"><h3>Reçineler</h3><p>Sanayi uygulamaları için özel
reçine geliştirme.</p></div>
<div id="kompozit-malzemeler"><h3>Kompozit Malzemeler</h3>
<p>Kompozit malzeme Ar-Ge çalışmaları.</p></div>
<div id="ozel-polimerler"><h3>Özel Polimerler ve Kimyasallar</h3>
<p>Müşteriye özel polimer ve kimyasal geliştirme.</p></div>
</div></section>
""")

get_or_create_page(evoco_site, "/ar-ge-hizmetleri", "Ar-Ge Hizmetleri", """
<section class="s_text_block pt48 pb48"><div class="container">
<h1>Ar-Ge Hizmetleri</h1>
<div id="rd"><h3>Ar-Ge</h3><p>Laboratuvarımızda formülasyon tasarımı,
sentez ve karakterizasyon.</p></div>
<div id="urun-gelistirme"><h3>Ürün Geliştirme</h3><p>Müşteri
ihtiyaçlarına özel ürün geliştirme hizmeti.</p></div>
<div id="proje-gelistirme"><h3>Proje Geliştirme</h3><p>Uçtan uca proje
geliştirme desteği.</p></div>
<div id="test-analiz"><h3>Test ve Analiz</h3><p>Fiziksel ve kimyasal
test/analiz hizmetleri.</p></div>
<div id="diger"><h3>Diğer Hizmetler</h3><p>Teknik danışmanlık ve
uygulama desteği.</p></div>
</div></section>
""")

env.cr.commit()

# -----------------------------------------------------------------------
# Blogs
# -----------------------------------------------------------------------
get_or_create_blog(areks_site, "Blog")
evoco_news = get_or_create_blog(evoco_site, "Haberler")
get_or_create_blog(evoco_site, "Teknik Makaleler")
env.cr.commit()

# -----------------------------------------------------------------------
# Rebuild menus to mirror the reference sites' structure
# -----------------------------------------------------------------------
def wipe_menus(site):
    menus = Menu.search([('website_id', '=', site.id)]).filtered(lambda m: m.url != '#')
    if menus:
        menus.unlink()


def build_menu_tree(site, tree):
    # explicit sequence (10, 20, 30, ...) so top-level order is always
    # "Ana Sayfa" first, then the rest in the given logical order -
    # website.menu otherwise defaults every item to sequence=40, which
    # falls back to creation-order (id) and can scramble the nav.
    for seq, item in enumerate(tree, start=1):
        name, url, children = item
        existing = Menu.search([('name', '=', name), ('website_id', '=', site.id)], limit=1)
        if existing:
            parent = existing
            if parent.sequence != seq * 10:
                parent.sequence = seq * 10
        else:
            parent = Menu.create({
                'name': name, 'url': url, 'website_id': site.id,
                'parent_id': site.menu_id.id, 'sequence': seq * 10,
            })
            # NOTE: website.menu.url is a COMPUTED field (_compute_url).
            # For a parent item with children and no linked page_id, it
            # deliberately resolves to '#' (pure dropdown toggle) - a
            # one-off write back to the intended url does NOT survive a
            # later recompute, so this is accepted as-is: clicking the
            # parent opens the dropdown instead of navigating, which is
            # standard behaviour for this kind of menu.
        for cname, curl in children:
            if not Menu.search([('name', '=', cname), ('website_id', '=', site.id), ('parent_id', '=', parent.id)], limit=1):
                Menu.create({'name': cname, 'url': curl, 'website_id': site.id, 'parent_id': parent.id})


wipe_menus(areks_site)
AREKS_TREE = [
    ("Ana Sayfa", "/", []),
    ("Kurumsal", "/hakkimizda", [
        ("Hakkımızda", "/hakkimizda"),
        ("Misyon & Vizyon", "/misyon-vizyon"),
        ("Kalite Politikamız", "/kalite-politikasi"),
    ]),
    ("Ürünlerimiz", "/shop", [
        ("Poliollar", cat_url("Polioller", areks_site)),
        ("İzosiyanatlar", cat_url("İzosiyanatlar", areks_site)),
        ("Yardımcı Kimyasallar", cat_url("Yardımcı Kimyasallar", areks_site)),
        ("Polyol Sistemleri", cat_url("Polyol Sistemleri", areks_site)),
    ]),
    ("Blog", "/blog", []),
    ("İletişim", "/contactus", []),
    ("Teklif İste", "/teklif-al", []),
]
build_menu_tree(areks_site, AREKS_TREE)

wipe_menus(evoco_site)
EVOCO_TREE = [
    ("Ana Sayfa", "/", []),
    ("Hakkımızda", "/hakkimizda", []),
    ("Araştırma Alanları", "/arastirma-alanlari", [
        ("Poliüretan", "/arastirma-alanlari#poliuretan"),
        ("Poliester Polioller", "/arastirma-alanlari#poliester-polioller"),
        ("Reçineler", "/arastirma-alanlari#recineler"),
        ("Kompozit Malzemeler", "/arastirma-alanlari#kompozit-malzemeler"),
        ("Özel Polimerler ve Kimyasallar", "/arastirma-alanlari#ozel-polimerler"),
    ]),
    ("Hizmetler", "/ar-ge-hizmetleri", [
        ("Ar-Ge", "/ar-ge-hizmetleri#rd"),
        ("Ürün Geliştirme", "/ar-ge-hizmetleri#urun-gelistirme"),
        ("Proje Geliştirme", "/ar-ge-hizmetleri#proje-gelistirme"),
        ("Test ve Analiz", "/ar-ge-hizmetleri#test-analiz"),
        ("Diğer Hizmetler", "/ar-ge-hizmetleri#diger"),
    ]),
    ("Blog", "/blog", []),
    ("İletişim", "/contactus", []),
]
build_menu_tree(evoco_site, EVOCO_TREE)

env.cr.commit()

# -----------------------------------------------------------------------
# Hero color update to match reference brand accents:
# Areks real site uses a "deep blue" theme -> keep/reinforce #0b3d62
# Evoco real site's accent color is literally #eb0e06 (red) on white/dark
# -----------------------------------------------------------------------
def recolor_homepage(site, old_bg, new_bg):
    page = Page.search([('url', '=', '/'), ('website_id', '=', site.id)], limit=1)
    view = page.view_id
    if old_bg in (view.arch_db or '') and old_bg != new_bg:
        view.arch_db = view.arch_db.replace(old_bg, new_bg)
        print(f"  [OK] recolored {site.name} homepage hero: {old_bg} -> {new_bg}")
    else:
        print(f"  [SKIP] {site.name} homepage hero color already set")


recolor_homepage(evoco_site, "#1b4332", "#eb0e06")

env.cr.commit()

print("=" * 70)
print("12d_reference_redesign.py done")
print("=" * 70)
