"""
12c_homepage_content.py
Per-website homepage hero section + company intro + contact info.

NOTE (found & fixed): website creation auto-generates a STANDALONE
per-website copy of the website.homepage view (reachable via
website.page, e.g. ir.ui.view id 3224 for site 190) - NOT an
inherited child of the generic `website.homepage` view. An earlier
version of this script added an `inherit_id`-based xpath override on
the generic view, which the ORM happily combined (verified via
get_view()) but which the live site never actually uses for routing,
since website.page.view_id points at the per-website standalone copy
instead. Editing that standalone view's arch_db directly is the
correct fix - done here.

Idempotent: only injects the hero markup if not already present in the
view's arch_db.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12c_homepage_content.py
"""

print("=" * 70)
print("12c_homepage_content.py starting")
print("=" * 70)

View = env['ir.ui.view'].sudo()
Page = env['website.page'].sudo()
Website = env['website'].sudo()

areks_site = Website.search([('name', '=', 'Areks Kimya')], limit=1)
evoco_site = Website.search([('name', '=', 'Evoco Polimer')], limit=1)

# clean up the earlier (ineffective) inherited views from the first attempt
stale = View.search([('name', 'in', ['Areks Homepage Hero', 'Evoco Homepage Hero'])])
if stale:
    print(f"  [OK] removing {len(stale)} stale inherited homepage view(s) from the first attempt")
    stale.unlink()
    env.cr.commit()

AREKS_HERO = """<section class="s_text_block pt64 pb64" style="background-color:#0b3d62;color:#ffffff;">
  <div class="container">
    <h1 class="display-4 fw-bold">Areks Kimya</h1>
    <p class="lead">Poliuretan hammaddelerinde güvenilir tedarik ortağınız.</p>
    <p>
      Areks Kimya Otomotiv San. ve Dış Tic. A.Ş., poliol, izosiyanat ve yardımcı
      kimyasal gruplarında, Pendik/İstanbul merkezli depo ve lojistik altyapısıyla
      sanayiye kesintisiz hammadde tedariği sağlar. Konvansiyonel ve polimerik
      poliollerden TDI/MDI serisi izosiyanatlara, katalist ve silikonlardan
      yanmazlık katkılarına kadar geniş bir ürün portföyü sunuyoruz.
    </p>
    <a href="/teklif-al" class="btn btn-light btn-lg mt-3">Teklif İste</a>
  </div>
</section>
<section class="s_text_block pt32 pb32">
  <div class="container">
    <h3>İletişim</h3>
    <p>
      Kiram Sk., Ankara Cd. No:4, Pendik, İstanbul 34906, Türkiye<br/>
      Tel: +90 216 378 64 51<br/>
      E-posta: info@arekschemicals.com
    </p>
  </div>
</section>"""

EVOCO_HERO = """<section class="s_text_block pt64 pb64" style="background-color:#1b4332;color:#ffffff;">
  <div class="container">
    <h1 class="display-4 fw-bold">Evoco Polimer</h1>
    <p class="lead">Poliüretan sistem geliştirmede Ar-Ge odaklı çözüm ortağınız.</p>
    <p>
      Evoco Polimer San. Tic. A.Ş., Gebze/Kocaeli'deki üretim tesisinde rijit panel,
      sprey izolasyon, soğutma, esnek köpük, semi-rigid ve CASE elastomer
      sistemleri geliştirir ve üretir. İnşaat &amp; yalıtım, soğutma, mobilya &amp;
      yatak, ses yalıtımı ve CASE uygulama alanlarına özel formüle edilmiş
      poliüretan sistemlerle müşterilerimizin ihtiyaçlarına göre çözümler sunarız.
    </p>
    <a href="/contactus" class="btn btn-light btn-lg mt-3">Bize Ulaşın</a>
  </div>
</section>
<section class="s_text_block pt32 pb32">
  <div class="container">
    <h3>İletişim</h3>
    <p>
      GOSB Kemal Nehrozoğlu Cd. No:507/9, Gebze, Kocaeli, Türkiye<br/>
      Tel: +90 262 678 88 30<br/>
      E-posta: info@evocopolymers.com
    </p>
  </div>
</section>"""


def set_hero(site, hero_html, label):
    page = Page.search([('url', '=', '/'), ('website_id', '=', site.id)], limit=1)
    assert page, f"no homepage website.page found for {site.name}"
    view = page.view_id
    if "s_text_block" in (view.arch_db or ""):
        print(f"  [SKIP] {label} hero already present on {site.name} (view id={view.id})")
        return
    new_arch = view.arch_db.replace(
        '<div id="wrap" class="oe_structure oe_empty"/>',
        f'<div id="wrap" class="oe_structure">{hero_html}</div>',
    )
    assert new_arch != view.arch_db, f"could not locate the empty wrap div on {label} homepage view {view.id}"
    view.arch_db = new_arch
    print(f"  [OK] hero content injected into {site.name} homepage (view id={view.id})")


set_hero(areks_site, AREKS_HERO, "Areks")
set_hero(evoco_site, EVOCO_HERO, "Evoco")

env.cr.commit()

print("=" * 70)
print("12c_homepage_content.py done")
print("=" * 70)
