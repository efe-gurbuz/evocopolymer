"""
12e_senior_redesign.py
Full visual redesign of both websites (replacing the earlier plain
text-block hero from 12c/12d) with a proper multi-section design:
real photography (curated, verified-live Unsplash images matching the
chemical/polyurethane industry), a coherent per-site color system,
stat/value-prop/showcase sections, and richer content pages.

Idempotent: re-running replaces content deterministically (search by
page url, always rewrite that page's wrap div - safe since this script
owns these specific pages/sections entirely).

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/12e_senior_redesign.py
"""

print("=" * 70)
print("12e_senior_redesign.py starting")
print("=" * 70)

Website = env['website'].sudo()
Page = env['website.page'].sudo()

areks_site = Website.search([('name', '=', 'Areks Kimya')], limit=1)
evoco_site = Website.search([('name', '=', 'Evoco Polimer')], limit=1)


def set_page_body(site, url, html_body, title=None):
    page = Page.search([('url', '=', url), ('website_id', '=', site.id)], limit=1)
    assert page, f"page not found: {site.name}{url}"
    view = page.view_id
    import re
    arch = view.arch_db
    new_inner = f'<div id="wrap" class="oe_structure">{html_body}</div>'
    if '<div id="wrap"' in arch:
        arch = re.sub(r'<div id="wrap".*?</div>\s*</t>\s*</t>\s*$', new_inner + '</t></t>', arch, flags=re.S)
        if '<div id="wrap"' in arch and new_inner not in arch:
            # fallback: replace from the wrap div to the matching end more loosely
            start = arch.find('<div id="wrap"')
            arch = arch[:start] + new_inner + '</t></t>'
    view.arch_db = arch
    page.is_published = True
    print(f"  [OK] content set: {site.name}{url}")


# =========================================================================
# Shared design tokens (duplicated per-page style block - no shared asset
# bundle wired up, kept simple/robust)
# =========================================================================
AREKS_CSS = """
<style>
.ak-hero{position:relative;min-height:560px;display:flex;align-items:center;background:#0b2438 url('https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=1600&q=70') center/cover no-repeat;}
.ak-hero:before{content:"";position:absolute;inset:0;background:linear-gradient(100deg,rgba(8,26,43,.94) 0%,rgba(8,26,43,.78) 45%,rgba(8,26,43,.45) 100%);}
.ak-hero .container{position:relative;z-index:1;}
.ak-eyebrow{color:#e8a33d;letter-spacing:2px;font-weight:600;font-size:.85rem;text-transform:uppercase;}
.ak-h1{color:#fff;font-weight:800;font-size:2.9rem;line-height:1.15;margin:.5rem 0 1.1rem;}
.ak-lead{color:#cfe0ee;font-size:1.15rem;max-width:560px;margin-bottom:1.8rem;}
.ak-btn-primary{background:#e8a33d;border-color:#e8a33d;color:#1a1304;font-weight:600;padding:.75rem 1.6rem;border-radius:4px;}
.ak-btn-primary:hover{background:#d6912d;color:#1a1304;}
.ak-btn-outline{border:2px solid #fff;color:#fff;font-weight:600;padding:.68rem 1.5rem;border-radius:4px;background:transparent;}
.ak-btn-outline:hover{background:#fff;color:#0b2438;}
.ak-stats{background:#0b3d62;padding:2.2rem 0;}
.ak-stat-num{color:#e8a33d;font-size:2.2rem;font-weight:800;}
.ak-stat-label{color:#cfe0ee;font-size:.9rem;}
.ak-section{padding:4.5rem 0;}
.ak-section-title{font-weight:800;color:#0b2438;font-size:2rem;margin-bottom:.6rem;}
.ak-section-sub{color:#5b6b7c;max-width:620px;margin:0 auto 2.5rem;}
.ak-card{background:#fff;border-radius:10px;box-shadow:0 6px 24px rgba(11,36,56,.08);padding:2rem 1.5rem;height:100%;text-align:center;transition:transform .2s;}
.ak-card:hover{transform:translateY(-4px);}
.ak-card i{font-size:2rem;color:#0b3d62;margin-bottom:1rem;}
.ak-card h5{font-weight:700;color:#0b2438;}
.ak-card p{color:#5b6b7c;font-size:.92rem;margin-bottom:0;}
.ak-prod-card{position:relative;border-radius:10px;overflow:hidden;height:260px;display:block;color:#fff;text-decoration:none;}
.ak-prod-card img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .35s;}
.ak-prod-card:hover img{transform:scale(1.07);}
.ak-prod-card:before{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(11,36,56,.92) 0%,rgba(11,36,56,.2) 60%);}
.ak-prod-card .ak-prod-body{position:absolute;left:0;right:0;bottom:0;padding:1.2rem;z-index:1;}
.ak-prod-card h5{color:#fff;font-weight:700;margin-bottom:.2rem;}
.ak-prod-card span{color:#e8a33d;font-size:.85rem;font-weight:600;}
.ak-split-img{border-radius:10px;overflow:hidden;}
.ak-split-img img{width:100%;height:100%;object-fit:cover;min-height:320px;}
.ak-bg-light{background:#f5f8fb;}
.ak-cta{background:linear-gradient(100deg,#0b2438,#0b3d62);padding:3.5rem 0;text-align:center;}
.ak-cta h3{color:#fff;font-weight:800;font-size:1.8rem;}
.ak-cta p{color:#cfe0ee;margin-bottom:1.5rem;}
.ak-page-banner{background:#0b2438 center/cover no-repeat;position:relative;padding:4.5rem 0;}
.ak-page-banner:before{content:"";position:absolute;inset:0;background:rgba(8,26,43,.65);}
.ak-page-banner .container{position:relative;z-index:1;}
.ak-page-banner h1{color:#fff;font-weight:800;margin:0;}
</style>
"""

EVOCO_CSS = """
<style>
.ev-hero{position:relative;min-height:560px;display:flex;align-items:center;background:#120505 url('https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1600&q=70') center/cover no-repeat;}
.ev-hero:before{content:"";position:absolute;inset:0;background:linear-gradient(100deg,rgba(10,4,4,.93) 0%,rgba(20,6,6,.8) 45%,rgba(30,8,8,.4) 100%);}
.ev-hero .container{position:relative;z-index:1;}
.ev-eyebrow{color:#ff5349;letter-spacing:2px;font-weight:600;font-size:.85rem;text-transform:uppercase;}
.ev-h1{color:#fff;font-weight:800;font-size:2.9rem;line-height:1.15;margin:.5rem 0 1.1rem;}
.ev-lead{color:#e9d6d4;font-size:1.15rem;max-width:580px;margin-bottom:1.8rem;}
.ev-btn-primary{background:#eb0e06;border-color:#eb0e06;color:#fff;font-weight:600;padding:.75rem 1.6rem;border-radius:4px;}
.ev-btn-primary:hover{background:#c20b05;color:#fff;}
.ev-btn-outline{border:2px solid #fff;color:#fff;font-weight:600;padding:.68rem 1.5rem;border-radius:4px;background:transparent;}
.ev-btn-outline:hover{background:#fff;color:#120505;}
.ev-stats{background:#161616;padding:2.2rem 0;}
.ev-stat-num{color:#eb0e06;font-size:2.2rem;font-weight:800;}
.ev-stat-label{color:#c9c9c9;font-size:.9rem;}
.ev-section{padding:4.5rem 0;}
.ev-section-title{font-weight:800;color:#161616;font-size:2rem;margin-bottom:.6rem;}
.ev-section-sub{color:#6b6b6b;max-width:620px;margin:0 auto 2.5rem;}
.ev-card{position:relative;border-radius:10px;overflow:hidden;height:280px;display:block;color:#fff;text-decoration:none;}
.ev-card img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .35s;}
.ev-card:hover img{transform:scale(1.07);}
.ev-card:before{content:"";position:absolute;inset:0;background:linear-gradient(0deg,rgba(10,4,4,.92) 0%,rgba(10,4,4,.1) 65%);}
.ev-card .ev-card-body{position:absolute;left:0;right:0;bottom:0;padding:1.2rem;z-index:1;}
.ev-card h5{color:#fff;font-weight:700;margin-bottom:.2rem;}
.ev-card span{color:#ff5349;font-size:.85rem;font-weight:600;}
.ev-split-img{border-radius:10px;overflow:hidden;}
.ev-split-img img{width:100%;height:100%;object-fit:cover;min-height:320px;}
.ev-bg-dark{background:#161616;}
.ev-bg-dark .ev-section-title, .ev-bg-dark h3{color:#fff;}
.ev-bg-dark .ev-section-sub, .ev-bg-dark p{color:#c9c9c9;}
.ev-cta{background:linear-gradient(100deg,#120505,#2a0a08);padding:3.5rem 0;text-align:center;}
.ev-cta h3{color:#fff;font-weight:800;font-size:1.8rem;}
.ev-cta p{color:#e9d6d4;margin-bottom:1.5rem;}
.ev-page-banner{background:#120505 center/cover no-repeat;position:relative;padding:4.5rem 0;}
.ev-page-banner:before{content:"";position:absolute;inset:0;background:rgba(10,4,4,.68);}
.ev-page-banner .container{position:relative;z-index:1;}
.ev-page-banner h1{color:#fff;font-weight:800;margin:0;}
.ev-icon-row{display:flex;gap:1rem;align-items:flex-start;margin-bottom:1.8rem;}
.ev-icon-row i{font-size:1.6rem;color:#eb0e06;margin-top:.2rem;}
.ev-icon-row h5{font-weight:700;margin-bottom:.3rem;}
.ev-icon-row p{color:#6b6b6b;margin-bottom:0;}
</style>
"""

# =========================================================================
# AREKS KİMYA — Homepage
# =========================================================================
cat_url = lambda name, site: (
    env['product.public.category'].sudo().search([('name', '=', name), ('website_id', '=', site.id)], limit=1).website_url or '/shop'
)

AREKS_HOME = AREKS_CSS + f"""
<section class="ak-hero">
  <div class="container">
    <div class="row"><div class="col-lg-8">
      <div class="ak-eyebrow">Poliuretan Hammadde Tedariki · 1998'den Beri</div>
      <h1 class="ak-h1">Endüstri İçin Güvenilir,<br/>Yüksek Performanslı Çözümler</h1>
      <p class="ak-lead">Poliol, izosiyanat ve yardımcı kimyasal gruplarında geniş ürün
      portföyümüz ve teknik bilgi birikimimizle, poliuretan üreticilerine
      kesintisiz ve güvenilir hammadde tedariği sağlıyoruz.</p>
      <a href="{cat_url('Polioller', areks_site)}" class="btn ak-btn-primary me-2">Ürünlerimizi İnceleyin</a>
      <a href="/teklif-al" class="btn ak-btn-outline">Teklif İste</a>
    </div></div>
  </div>
</section>

<div class="ak-stats">
  <div class="container"><div class="row text-center g-4">
    <div class="col-6 col-md-3"><div class="ak-stat-num">25+</div><div class="ak-stat-label">Yıllık Sektör Tecrübesi</div></div>
    <div class="col-6 col-md-3"><div class="ak-stat-num">27+</div><div class="ak-stat-label">Aktif Ürün Kalemi</div></div>
    <div class="col-6 col-md-3"><div class="ak-stat-num">4</div><div class="ak-stat-label">Kıtadan Tedarikçi Ağı</div></div>
    <div class="col-6 col-md-3"><div class="ak-stat-num">7/24</div><div class="ak-stat-label">Lojistik &amp; Depo Desteği</div></div>
  </div></div>
</div>

<section class="ak-section">
  <div class="container text-center">
    <h2 class="ak-section-title">Neden Areks Kimya?</h2>
    <p class="ak-section-sub mx-auto">Pendik'teki depo ve lojistik altyapımızla, sanayiye
    kesintisiz hammadde akışı sağlıyoruz.</p>
    <div class="row g-4">
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-tags"></i><h5>Rekabetçi Fiyat</h5><p>Geniş tedarikçi ağımızla en uygun maliyetli çözümler.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-headset"></i><h5>Sürekli Destek</h5><p>Teknik ekibimizle süreç boyunca yanınızdayız.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-truck"></i><h5>Zamanında Teslimat</h5><p>Planlı lojistik ile kesintisiz üretim desteği.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-certificate"></i><h5>Kalite Anlayışı</h5><p>Parti bazında izlenebilirlik ve kalite kontrolü.</p></div></div>
    </div>
  </div>
</section>

<section class="ak-section ak-bg-light">
  <div class="container text-center">
    <h2 class="ak-section-title">Ürün Gruplarımız</h2>
    <p class="ak-section-sub mx-auto">Poliuretan üretiminin her aşaması için geniş hammadde yelpazesi.</p>
    <div class="row g-4 text-start">
      <div class="col-md-6 col-lg-3"><a class="ak-prod-card" href="{cat_url('Polioller', areks_site)}">
        <img src="https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=500&q=65"/>
        <div class="ak-prod-body"><span>8 ÜRÜN</span><h5>Poliollar</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ak-prod-card" href="{cat_url('İzosiyanatlar', areks_site)}">
        <img src="https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=500&q=65"/>
        <div class="ak-prod-body"><span>4 ÜRÜN</span><h5>İzosiyanatlar</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ak-prod-card" href="{cat_url('Yardımcı Kimyasallar', areks_site)}">
        <img src="https://images.unsplash.com/photo-1605152276897-4f618f831968?w=500&q=65"/>
        <div class="ak-prod-body"><span>15 ÜRÜN</span><h5>Yardımcı Kimyasallar</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ak-prod-card" href="{cat_url('Polyol Sistemleri', areks_site)}">
        <img src="https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=500&q=65"/>
        <div class="ak-prod-body"><span>GRUP ŞİRKETİ</span><h5>Polyol Sistemleri</h5></div></a></div>
    </div>
  </div>
</section>

<section class="ak-section">
  <div class="container">
    <div class="row align-items-center g-5">
      <div class="col-lg-6"><div class="ak-split-img">
        <img src="https://images.unsplash.com/photo-1587293852726-70cdb56c2866?w=900&q=70"/>
      </div></div>
      <div class="col-lg-6">
        <div class="ak-eyebrow" style="color:#0b3d62">Tedarik Zinciri</div>
        <h2 class="ak-section-title">Pendik'ten Türkiye Geneline<br/>Kesintisiz Lojistik</h2>
        <p style="color:#5b6b7c">İstanbul Pendik'teki merkez depomuzdan, yurt içi ve yurt
        dışı tedarikçi ağımızla beslenen stoklarımızı, poliuretan üreticilerine
        zamanında ve güvenli şekilde ulaştırıyoruz. Lot bazlı izlenebilirlik ve
        FEFO stok yönetimi ile ürün tazeliğini garanti ediyoruz.</p>
        <a href="/hakkimizda" class="btn" style="background:#0b3d62;color:#fff;font-weight:600;border-radius:4px;padding:.65rem 1.4rem;">Hakkımızda</a>
      </div>
    </div>
  </div>
</section>

<div class="ak-cta">
  <div class="container">
    <h3>İhtiyacınız olan hammaddeyi bugün teklif alın</h3>
    <p>Satış ekibimiz 24 saat içinde sizinle iletişime geçsin.</p>
    <a href="/teklif-al" class="btn ak-btn-primary">Teklif İste</a>
  </div>
</div>
"""

set_page_body(areks_site, "/", AREKS_HOME)
env.cr.commit()
print("  [OK] Areks homepage rebuilt")

# =========================================================================
# EVOCO POLİMER — Homepage
# =========================================================================
EVOCO_HOME = EVOCO_CSS + f"""
<section class="ev-hero">
  <div class="container">
    <div class="row"><div class="col-lg-8">
      <div class="ev-eyebrow">Gebze Ar-Ge Laboratuvarı &amp; Üretim Tesisi</div>
      <h1 class="ev-h1">Ar-Ge Odaklı<br/>Poliüretan Sistem Çözümleri</h1>
      <p class="ev-lead">Rijit panel, sprey izolasyon, soğutma, esnek köpük, semi-rigid
      ve CASE elastomer sistemlerinde, laboratuvarımızda geliştirdiğimiz özel
      formülasyonlarla müşterilerimize değer katıyoruz.</p>
      <a href="/arastirma-alanlari" class="btn ev-btn-primary me-2">Araştırma Alanlarımız</a>
      <a href="/contactus" class="btn ev-btn-outline">Bize Ulaşın</a>
    </div></div>
  </div>
</section>

<div class="ev-stats">
  <div class="container"><div class="row text-center g-4">
    <div class="col-6 col-md-3"><div class="ev-stat-num">5</div><div class="ev-stat-label">Araştırma Alanı</div></div>
    <div class="col-6 col-md-3"><div class="ev-stat-num">8+</div><div class="ev-stat-label">Poliüretan Sistemi</div></div>
    <div class="col-6 col-md-3"><div class="ev-stat-num">2</div><div class="ev-stat-label">Formül Varyantı (RP210)</div></div>
    <div class="col-6 col-md-3"><div class="ev-stat-num">Gebze</div><div class="ev-stat-label">Kocaeli Üretim Tesisi</div></div>
  </div></div>
</div>

<section class="ev-section">
  <div class="container text-center">
    <h2 class="ev-section-title">Araştırma Alanlarımız</h2>
    <p class="ev-section-sub mx-auto">Laboratuvarımızda beş ana alanda formülasyon
    geliştirme ve karakterizasyon çalışmaları yürütüyoruz.</p>
    <div class="row g-4 text-start">
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/arastirma-alanlari#poliuretan">
        <img src="https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=500&q=65"/>
        <div class="ev-card-body"><span>ARAŞTIRMA</span><h5>Poliüretan</h5></div></a></div>
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/arastirma-alanlari#poliester-polioller">
        <img src="https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=500&q=65"/>
        <div class="ev-card-body"><span>ARAŞTIRMA</span><h5>Poliester Polioller</h5></div></a></div>
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/arastirma-alanlari#recineler">
        <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?w=500&q=65"/>
        <div class="ev-card-body"><span>ARAŞTIRMA</span><h5>Reçineler</h5></div></a></div>
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/arastirma-alanlari#kompozit-malzemeler">
        <img src="https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=500&q=65"/>
        <div class="ev-card-body"><span>ARAŞTIRMA</span><h5>Kompozit Malzemeler</h5></div></a></div>
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/arastirma-alanlari#ozel-polimerler">
        <img src="https://images.unsplash.com/photo-1603126857599-f6e157fa2fe6?w=500&q=65"/>
        <div class="ev-card-body"><span>ARAŞTIRMA</span><h5>Özel Polimerler ve Kimyasallar</h5></div></a></div>
      <div class="col-md-6 col-lg-4"><a class="ev-card" href="/ar-ge-hizmetleri">
        <img src="https://images.unsplash.com/photo-1605152276897-4f618f831968?w=500&q=65"/>
        <div class="ev-card-body"><span>TÜMÜNÜ GÖR</span><h5>Hizmetlerimiz</h5></div></a></div>
    </div>
  </div>
</section>

<section class="ev-section ev-bg-dark">
  <div class="container">
    <div class="row align-items-center g-5">
      <div class="col-lg-6 order-lg-2"><div class="ev-split-img">
        <img src="https://images.unsplash.com/photo-1513828583688-c52646db42da?w=900&q=70"/>
      </div></div>
      <div class="col-lg-6 order-lg-1">
        <div class="ev-eyebrow">Ar-Ge Yaklaşımımız</div>
        <h3>Laboratuvardan Sahaya,<br/>Uçtan Uca Ürün Geliştirme</h3>
        <p>Müşteri ihtiyacından yola çıkarak formülasyon tasarımı, numune üretimi,
        test &amp; analiz ve proje devreye alma aşamalarının tamamında
        yanınızdayız. EVO-RP 210 gibi sistemlerimizde birden fazla formül
        varyantını (ör. Cyclopentane / 365MFC bazlı) paralel geliştirip
        performans ve maliyet dengesini optimize ediyoruz.</p>
        <a href="/ar-ge-hizmetleri" class="btn ev-btn-primary">Hizmetlerimizi İnceleyin</a>
      </div>
    </div>
  </div>
</section>

<section class="ev-section">
  <div class="container text-center">
    <h2 class="ev-section-title">Hizmetlerimiz</h2>
    <p class="ev-section-sub mx-auto">Ar-Ge'den saha uygulamasına kadar tüm proje sürecinde destek.</p>
    <div class="row g-4 text-start">
      <div class="col-md-6 col-lg-3"><a class="ev-card" style="height:220px" href="/ar-ge-hizmetleri#rd">
        <img src="https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=500&q=65"/>
        <div class="ev-card-body"><h5>Ar-Ge</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ev-card" style="height:220px" href="/ar-ge-hizmetleri#urun-gelistirme">
        <img src="https://images.unsplash.com/photo-1581093588401-fbb62a02f120?w=500&q=65"/>
        <div class="ev-card-body"><h5>Ürün Geliştirme</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ev-card" style="height:220px" href="/ar-ge-hizmetleri#proje-gelistirme">
        <img src="https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=500&q=65"/>
        <div class="ev-card-body"><h5>Proje Geliştirme</h5></div></a></div>
      <div class="col-md-6 col-lg-3"><a class="ev-card" style="height:220px" href="/ar-ge-hizmetleri#test-analiz">
        <img src="https://images.unsplash.com/photo-1603126857599-f6e157fa2fe6?w=500&q=65"/>
        <div class="ev-card-body"><h5>Test ve Analiz</h5></div></a></div>
    </div>
  </div>
</section>

<div class="ev-cta">
  <div class="container">
    <h3>Projeniz için formülasyon desteğine mi ihtiyacınız var?</h3>
    <p>Ar-Ge ekibimiz talebinizi değerlendirsin.</p>
    <a href="/contactus" class="btn ev-btn-primary">Bize Ulaşın</a>
  </div>
</div>
"""

set_page_body(evoco_site, "/", EVOCO_HOME)
env.cr.commit()
print("  [OK] Evoco homepage rebuilt")

# =========================================================================
# AREKS content pages
# =========================================================================
AREKS_HAKKIMIZDA = AREKS_CSS + """
<div class="ak-page-banner" style="background-image:url('https://images.unsplash.com/photo-1587293852726-70cdb56c2866?w=1600&q=65')">
  <div class="container"><h1>Hakkımızda</h1></div>
</div>
<section class="ak-section">
  <div class="container">
    <div class="row g-5 align-items-center">
      <div class="col-lg-6">
        <div class="ak-eyebrow">1998'den Beri</div>
        <h2 class="ak-section-title">Poliuretan Hammadde Tedarikinde<br/>Güvenilir İş Ortağınız</h2>
        <p style="color:#5b6b7c">Areks Kimya Otomotiv San. ve Dış Tic. A.Ş., poliuretan
        endüstrisine yönelik hammadde tedarikinde 25 yılı aşan deneyimiyle,
        poliol, izosiyanat ve yardımcı kimyasal gruplarında sanayiye kesintisiz
        ve güvenilir tedarik sağlar. İstanbul Pendik'teki merkez depomuzdan,
        yurt içi ve yurt dışı tedarikçi ortaklarımızla beslenen geniş stok
        kapasitemizle müşterilerimizin yanındayız.</p>
      </div>
      <div class="col-lg-6"><div class="ak-split-img">
        <img src="https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=900&q=70"/>
      </div></div>
    </div>
  </div>
</section>
<section class="ak-section ak-bg-light text-center">
  <div class="container">
    <h2 class="ak-section-title">Neden Areks Kimya?</h2>
    <div class="row g-4 mt-2">
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-tags"></i><h5>Rekabetçi Fiyat</h5><p>Geniş tedarikçi ağımızla en uygun maliyetli çözümler.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-headset"></i><h5>Sürekli Destek</h5><p>Teknik ekibimizle süreç boyunca yanınızdayız.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-truck"></i><h5>Zamanında Teslimat</h5><p>Planlı lojistik ile kesintisiz üretim desteği.</p></div></div>
      <div class="col-md-3 col-6"><div class="ak-card"><i class="fa fa-certificate"></i><h5>Kalite Anlayışı</h5><p>Parti bazında izlenebilirlik ve kalite kontrolü.</p></div></div>
    </div>
  </div>
</section>
<div class="ak-cta">
  <div class="container"><h3>Ekibimizle tanışmak ister misiniz?</h3>
  <p>Sorularınız için bize ulaşın.</p>
  <a href="/contactus" class="btn ak-btn-primary">İletişime Geç</a></div>
</div>
"""
set_page_body(areks_site, "/hakkimizda", AREKS_HAKKIMIZDA)

AREKS_MISYON = AREKS_CSS + """
<div class="ak-page-banner" style="background-image:url('https://images.unsplash.com/photo-1605152276897-4f618f831968?w=1600&q=65')">
  <div class="container"><h1>Misyon &amp; Vizyon</h1></div>
</div>
<section class="ak-section">
  <div class="container">
    <div class="row g-4">
      <div class="col-lg-6"><div class="ak-card" style="text-align:left">
        <i class="fa fa-bullseye"></i>
        <h5>Misyonumuz</h5>
        <p>Poliuretan üreticilerine, geniş ürün portföyümüz ve teknik bilgi
        birikimimizle yüksek performanslı, güvenilir hammadde çözümleri
        sunarak üretim süreçlerinin kesintisiz işlemesine katkı sağlamak.</p>
      </div></div>
      <div class="col-lg-6"><div class="ak-card" style="text-align:left">
        <i class="fa fa-eye"></i>
        <h5>Vizyonumuz</h5>
        <p>Türkiye ve çevre bölgede poliuretan hammadde tedarikinde ilk
        tercih edilen, kalite ve güvenilirlikte referans gösterilen iş
        ortağı olmak.</p>
      </div></div>
    </div>
  </div>
</section>
"""
set_page_body(areks_site, "/misyon-vizyon", AREKS_MISYON)

AREKS_KALITE = AREKS_CSS + """
<div class="ak-page-banner" style="background-image:url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1600&q=65')">
  <div class="container"><h1>Kalite Politikamız</h1></div>
</div>
<section class="ak-section">
  <div class="container">
    <div class="row g-5 align-items-center">
      <div class="col-lg-5"><div class="ak-split-img">
        <img src="https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=700&q=70"/>
      </div></div>
      <div class="col-lg-7">
        <p style="color:#5b6b7c;font-size:1.05rem">Areks Kimya olarak; ürün kalitesinden ödün
        vermeden, sürdürülebilir tedarik zinciri yönetimi ve sürekli
        iyileştirme ilkesiyle çalışırız. Tüm hammaddelerimiz, uluslararası
        kalite standartlarına uygun tedarikçilerden temin edilir ve parti
        bazında (lot) izlenebilirlik sağlanır.</p>
        <ul style="color:#5b6b7c">
          <li>Her hammadde için lot/parti bazlı tam izlenebilirlik</li>
          <li>Son kullanma tarihi takibi ve FEFO stok yönetimi</li>
          <li>Tedarikçi bazında kalite değerlendirmesi</li>
          <li>ICIS referanslı şeffaf piyasa fiyatlandırması</li>
        </ul>
      </div>
    </div>
  </div>
</section>
"""
set_page_body(areks_site, "/kalite-politikasi", AREKS_KALITE)

AREKS_TEKLIF = AREKS_CSS + """
<div class="ak-page-banner" style="background-image:url('https://images.unsplash.com/photo-1605152276897-4f618f831968?w=1600&q=65')">
  <div class="container"><h1>Teklif İste</h1></div>
</div>
<section class="ak-section text-center">
  <div class="container">
    <p class="ak-section-sub mx-auto" style="color:#5b6b7c">İhtiyacınız olan hammadde ve
    miktarı belirtin, satış ekibimiz en kısa sürede sizinle iletişime geçsin.</p>
    <a href="/contactus" class="btn ak-btn-primary btn-lg">İletişim Formuna Git</a>
  </div>
</section>
"""
set_page_body(areks_site, "/teklif-al", AREKS_TEKLIF)

env.cr.commit()
print("  [OK] Areks content pages rebuilt")

# =========================================================================
# EVOCO content pages
# =========================================================================
EVOCO_HAKKIMIZDA = EVOCO_CSS + """
<div class="ev-page-banner" style="background-image:url('https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1600&q=65')">
  <div class="container"><h1>Hakkımızda</h1></div>
</div>
<section class="ev-section">
  <div class="container">
    <div class="row g-5 align-items-center">
      <div class="col-lg-6">
        <div class="ev-eyebrow">Gebze / Kocaeli</div>
        <h2 class="ev-section-title">Ar-Ge Laboratuvarından<br/>Seri Üretime</h2>
        <p style="color:#6b6b6b">Evoco Polimer San. Tic. A.Ş., Gebze/Kocaeli'deki Ar-Ge
        laboratuvarı ve üretim tesisinde poliüretan, poliester poliol, reçine
        ve kompozit malzeme alanlarında özel formülasyonlar geliştirir.
        Rijit panel, sprey izolasyon, soğutma, esnek köpük, semi-rigid ve
        CASE elastomer sistemlerinde, müşteri ihtiyacına özel çözümler
        üretiyoruz.</p>
      </div>
      <div class="col-lg-6"><div class="ev-split-img">
        <img src="https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=900&q=70"/>
      </div></div>
    </div>
  </div>
</section>
<section class="ev-section ev-bg-dark text-center">
  <div class="container">
    <h2>Ar-Ge Yetkinliklerimiz</h2>
    <div class="row g-4 mt-2 text-start">
      <div class="col-md-4"><div class="ev-icon-row"><i class="fa fa-flask"></i>
        <div><h5 style="color:#fff">Formülasyon Geliştirme</h5><p>Müşteri ihtiyacına özel reçete tasarımı.</p></div></div></div>
      <div class="col-md-4"><div class="ev-icon-row"><i class="fa fa-vial"></i>
        <div><h5 style="color:#fff">Test &amp; Analiz</h5><p>Fiziksel ve kimyasal karakterizasyon.</p></div></div></div>
      <div class="col-md-4"><div class="ev-icon-row"><i class="fa fa-industry"></i>
        <div><h5 style="color:#fff">Seri Üretime Geçiş</h5><p>Laboratuvardan sahaya ölçeklendirme.</p></div></div></div>
    </div>
  </div>
</section>
"""
set_page_body(evoco_site, "/hakkimizda", EVOCO_HAKKIMIZDA)

EVOCO_ARASTIRMA = EVOCO_CSS + """
<div class="ev-page-banner" style="background-image:url('https://images.unsplash.com/photo-1603126857599-f6e157fa2fe6?w=1600&q=65')">
  <div class="container"><h1>Araştırma Alanları</h1></div>
</div>
<section class="ev-section">
  <div class="container">
    <div id="poliuretan" class="row g-5 align-items-center mb-5 pb-4" style="border-bottom:1px solid #eee">
      <div class="col-lg-5"><div class="ev-split-img"><img src="https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=700&q=70"/></div></div>
      <div class="col-lg-7"><h3>Poliüretan</h3><p style="color:#6b6b6b">Rijit, esnek ve
      semi-rigid poliüretan sistemleri için formülasyon geliştirme. EVO-RP 210
      gibi sistemlerde birden fazla formül varyantı paralel olarak geliştirilir.</p></div>
    </div>
    <div id="poliester-polioller" class="row g-5 align-items-center mb-5 pb-4" style="border-bottom:1px solid #eee">
      <div class="col-lg-5 order-lg-2"><div class="ev-split-img"><img src="https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=700&q=70"/></div></div>
      <div class="col-lg-7 order-lg-1"><h3>Poliester Polioller</h3><p style="color:#6b6b6b">CASE
      ve özel uygulamalar için poliester esaslı poliol üretimi ve geliştirme.</p></div>
    </div>
    <div id="recineler" class="row g-5 align-items-center mb-5 pb-4" style="border-bottom:1px solid #eee">
      <div class="col-lg-5"><div class="ev-split-img"><img src="https://images.unsplash.com/photo-1562408590-e32931084e23?w=700&q=70"/></div></div>
      <div class="col-lg-7"><h3>Reçineler</h3><p style="color:#6b6b6b">Sanayi uygulamaları
      için özel reçine formülasyonu geliştirme çalışmaları.</p></div>
    </div>
    <div id="kompozit-malzemeler" class="row g-5 align-items-center mb-5 pb-4" style="border-bottom:1px solid #eee">
      <div class="col-lg-5 order-lg-2"><div class="ev-split-img"><img src="https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=700&q=70"/></div></div>
      <div class="col-lg-7 order-lg-1"><h3>Kompozit Malzemeler</h3><p style="color:#6b6b6b">Kompozit
      malzeme Ar-Ge çalışmaları ve uygulama geliştirme.</p></div>
    </div>
    <div id="ozel-polimerler" class="row g-5 align-items-center">
      <div class="col-lg-5"><div class="ev-split-img"><img src="https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=700&q=70"/></div></div>
      <div class="col-lg-7"><h3>Özel Polimerler ve Kimyasallar</h3><p style="color:#6b6b6b">Müşteriye
      özel polimer ve kimyasal geliştirme, karakterizasyon ve ölçeklendirme.</p></div>
    </div>
  </div>
</section>
"""
set_page_body(evoco_site, "/arastirma-alanlari", EVOCO_ARASTIRMA)

EVOCO_HIZMETLER = EVOCO_CSS + """
<div class="ev-page-banner" style="background-image:url('https://images.unsplash.com/photo-1581093588401-fbb62a02f120?w=1600&q=65')">
  <div class="container"><h1>Ar-Ge Hizmetleri</h1></div>
</div>
<section class="ev-section">
  <div class="container">
    <div class="row g-4">
      <div class="col-md-6" id="rd"><div class="ev-icon-row"><i class="fa fa-flask"></i>
        <div><h5>Ar-Ge</h5><p>Laboratuvarımızda formülasyon tasarımı, sentez ve karakterizasyon.</p></div></div></div>
      <div class="col-md-6" id="urun-gelistirme"><div class="ev-icon-row"><i class="fa fa-lightbulb"></i>
        <div><h5>Ürün Geliştirme</h5><p>Müşteri ihtiyaçlarına özel ürün geliştirme hizmeti.</p></div></div></div>
      <div class="col-md-6" id="proje-gelistirme"><div class="ev-icon-row"><i class="fa fa-diagram-project"></i>
        <div><h5>Proje Geliştirme</h5><p>Uçtan uca proje geliştirme ve devreye alma desteği.</p></div></div></div>
      <div class="col-md-6" id="test-analiz"><div class="ev-icon-row"><i class="fa fa-vial"></i>
        <div><h5>Test ve Analiz</h5><p>Fiziksel ve kimyasal test/analiz hizmetleri.</p></div></div></div>
      <div class="col-md-6" id="diger"><div class="ev-icon-row"><i class="fa fa-handshake"></i>
        <div><h5>Diğer Hizmetler</h5><p>Teknik danışmanlık ve saha uygulama desteği.</p></div></div></div>
    </div>
  </div>
</section>
<div class="ev-cta">
  <div class="container"><h3>Projenizi konuşalım</h3><p>Ar-Ge ekibimiz sizinle iletişime geçsin.</p>
  <a href="/contactus" class="btn ev-btn-primary">Bize Ulaşın</a></div>
</div>
"""
set_page_body(evoco_site, "/ar-ge-hizmetleri", EVOCO_HIZMETLER)

env.cr.commit()
print("  [OK] Evoco content pages rebuilt")
