"""
11b_spreadsheet_dashboards.py
Two LIVE pivot/chart Spreadsheet Dashboards (audit tur 4, points 2-3 -
rewritten a third time, now fixing why they rendered EMPTY):

  - Dashboard 192 "Formül Karşılaştırma – EVO-RP 210" was empty because
    its pivot measure (qty_produced) lived on mrp.production, where
    that field is NOT stored (store=False, computed) - the Odoo pivot
    data source aggregates via SQL read_group, which cannot group a
    non-stored field. Moved the cost/qty measures to mrp.report (the
    manufacturing analysis reporting model), which stores unit_cost,
    unit_component_cost and qty_produced for real. A second,
    rows-less mrp.production pivot (duration avg, product_qty sum)
    is kept for the KPI-style totals the audit also asked for.
  - Dashboard 193 "Satınalma Performansı – ICIS"'s pivot showed data
    but its CHART was empty - root cause found by hand-verifying the
    aggregation with _read_group(): the OLD (archived) Areks company's
    leftover purchase.order.line rows still matched the bare
    ('x_icis_price', '>', 0) domain and got grouped alongside the new
    company's rows under the SAME vendor display name, giving two
    silently-coexisting "Nordpol Chemie GmbH"-named groups (etc.) -
    the exact same "old-company-data-leak" root cause documented
    throughout this project. Added an explicit company_id filter.
    Expected (verified live via _read_group before writing this):
    Anatolia ~-0.48, Eastbridge ~1.02, Gulfstream ~0.59, Nordpol ~0.92
    (task's "-0.5 / +1.0 / +0.6 / +0.9").

Figure/pivot/cell structure this time is templated byte-for-byte on
this database's own working "Purchase & Vendor analysis" dashboard
(id 187): the bulk pivot spill formula "=PIVOT(id,N,FALSE,FALSE)"
(from its "Top Purchased Products" sheet) and, for the bar chart, its
"Top Vendors by Amount" carousel figure - a chart whose dataSource is
"range" (reading the already-computed, already-correctly-aggregated
pivot cells on the SAME sheet), not a second independent live Odoo
query. This was switched deliberately from the previous "dataSource:
odoo" (direct live query) version used in audit tur 3: a direct-query
chart has no way to request a specific aggregator (avg vs sum) in its
JSON - it silently defaults however the ORM aggregates a measure with
no explicit aggregator metadata (likely sum), which would NOT match
the pivot's own explicit "avg". Reading the chart's data from the
pivot's own spilled, already-avg'd cells guarantees both show the
exact same number.

Idempotent: search by dashboard name before create; existing
dashboards are overwritten in place (same id) so the live JSON stays
current.

Run with:
    odoo-bin shell --stop-after-init < /home/odoo/demo_setup/11b_spreadsheet_dashboards.py
"""

import json
import uuid

print("=" * 70)
print("11b_spreadsheet_dashboards.py starting")
print("=" * 70)

Dashboard = env['spreadsheet.dashboard'].sudo()
Group = env['spreadsheet.dashboard.group'].sudo()

areks = env['res.company'].sudo().search([('name', '=', 'Areks Kimya Otomotiv San. ve Dış Tic. A.Ş.')], limit=1)
evoco = env['res.company'].sudo().search([('name', '=', 'Evoco Polimer San. Tic. A.Ş.')], limit=1)
assert areks and evoco

rp210 = env['product.template'].sudo().search([('default_code', '=', 'EVO-RP 210')], limit=1)
assert rp210, "EVO-RP 210 not found - run 04_products.py first"

SPREADSHEET_VERSION = "19.3.10"  # verified live from this DB's own working dashboards


def new_sheet(sheet_id, name, formula_rows, figures):
    cells = {}
    for addr, formula in formula_rows:
        cells[addr] = formula  # bare string, matching the real dashboards' own cell shape
    return {
        "id": sheet_id,
        "name": name,
        "colNumber": 15,
        "rowNumber": 60,
        "rows": {},
        "cols": {},
        "merges": [],
        "cells": cells,
        "styles": {},
        "formats": {},
        "borders": {},
        "conditionalFormats": [],
        "dataValidationRules": [],
        "figures": figures,
        "tables": [],
        "areGridLinesVisible": True,
        "isVisible": True,
        "headerGroups": [],
        "comments": {},
    }


def make_bar_carousel_from_range(chart_title, sheet_name, label_range, data_range, offset_y):
    """ Verbatim structure (field-for-field) of the real "Top Vendors by
    Amount" carousel/combo/range chart in this DB's own "Purchase &
    Vendor analysis" dashboard (id 187) - a single bar series version
    (that real one mixes bar+line across two measures; we only need
    one measure so dataSetStyles only has entry "0"). """
    chart_id = str(uuid.uuid4())
    return {
        "id": str(uuid.uuid4()),
        "col": 0,
        "row": 0,
        "offset": {"x": 0, "y": offset_y},
        "width": 600,
        "height": 360,
        "tag": "carousel",
        "data": {
            "chartDefinitions": {
                chart_id: {
                    "type": "combo",
                    "legendPosition": "top",
                    "title": {"text": "", "align": "center", "bold": True},
                    "aggregated": False,
                    "humanize": True,
                    "dataSource": {
                        "labelRange": f"{sheet_name}!{label_range}",
                        "type": "range",
                        "dataSets": [{"dataSetId": "0", "dataRange": f"{sheet_name}!{data_range}"}],
                        "dataSetsHaveTitle": True,
                    },
                    "dataSetStyles": {"0": {"yAxisId": "y", "type": "bar"}},
                },
            },
            "title": {"text": chart_title, "bold": True, "fontSize": 21, "color": "#01666B"},
            "items": [{"type": "chart", "chartId": chart_id}],
            "fieldMatching": {},
        },
    }


def build_doc(sheet, pivots, next_pivot_id):
    return {
        "version": SPREADSHEET_VERSION,
        "sheets": [sheet],
        "styles": {},
        "formats": {},
        "borders": {},
        "revisionId": str(uuid.uuid4()),
        "uniqueFigureIds": [],
        "settings": {"locale": {"code": "tr_TR", "name": "Turkish"}},
        "pivots": pivots,
        "pivotNextId": next_pivot_id,
        "customTableStyles": {},
        "namedRanges": [],
        "globalFilters": [],
        "lists": {},
        "listNextId": 1,
        "odooLinkReferences": {},
    }


def get_or_create_group(name):
    grp = Group.search([('name', '=', name)], limit=1)
    if grp:
        return grp
    grp = Group.create({'name': name, 'sequence': 100})
    print(f"  [OK] dashboard group created: {name}")
    return grp


def upsert_dashboard(name, group, doc):
    existing = Dashboard.search([('name', '=', name)], limit=1)
    data = json.dumps(doc)
    if existing:
        existing.write({'spreadsheet_data': data, 'dashboard_group_id': group.id, 'is_published': True})
        print(f"  [OK] dashboard updated (version={doc['version']}): {name} (id={existing.id})")
        return existing
    dash = Dashboard.create({
        'name': name,
        'dashboard_group_id': group.id,
        'spreadsheet_data': data,
        'is_published': True,
    })
    print(f"  [OK] dashboard created (version={doc['version']}): {name} (id={dash.id})")
    return dash


group = get_or_create_group("Areks Group Demo")

# -----------------------------------------------------------------------
# 1. "Formül Karşılaştırma - EVO-RP 210"
#    Pivot 1 (mrp.report, rows=production_id.bom_id): unit_cost,
#    unit_component_cost, qty_produced -> spills A1:D3.
#    Pivot 2 (mrp.production, no rows - single total): duration,
#    product_qty -> spills further down at A10.
#    Chart: bar, reading pivot 1's own spilled B column (unit_cost).
# -----------------------------------------------------------------------
pivot1_domain = [["product_id.product_tmpl_id", "=", rp210.id], ["company_id", "=", evoco.id]]
pivot2_domain = [["product_id.product_tmpl_id", "=", rp210.id], ["state", "=", "done"], ["company_id", "=", evoco.id]]
pivots1 = {
    "1": {
        "type": "ODOO",
        "id": "1",
        "domain": pivot1_domain,
        "context": {},
        "sortedColumn": None,
        "measures": [
            {"id": "unit_cost", "fieldName": "unit_cost", "aggregator": "avg"},
            {"id": "unit_component_cost", "fieldName": "unit_component_cost", "aggregator": "avg"},
            {"id": "qty_produced", "fieldName": "qty_produced", "aggregator": "sum"},
        ],
        "model": "mrp.report",
        "columns": [],
        "rows": [{"fieldName": "production_id.bom_id"}],
        "name": "EVO-RP 210 - Maliyet Analizi (Formül)",
        "formulaId": "1",
        "fieldMatching": {},
        "filters": [],
    },
    "2": {
        "type": "ODOO",
        "id": "2",
        "domain": pivot2_domain,
        "context": {},
        "sortedColumn": None,
        "measures": [
            {"id": "duration", "fieldName": "duration", "aggregator": "avg"},
            {"id": "product_qty", "fieldName": "product_qty", "aggregator": "sum"},
        ],
        "model": "mrp.production",
        "columns": [],
        "rows": [],
        "name": "EVO-RP 210 - Üretim Toplamları",
        "formulaId": "2",
        "fieldMatching": {},
        "filters": [],
    },
}
sheet1 = new_sheet(
    str(uuid.uuid4()), "Formül Karşılaştırma",
    [
        ("A1", "=PIVOT(1,50,FALSE,FALSE)"),
        ("A9", "Üretim Toplamları (tüm EVO-RP 210, done MO'lar)"),
        ("A10", "=PIVOT(2,10,FALSE,FALSE)"),
    ],
    figures=[make_bar_carousel_from_range(
        "Formül Başına kg Maliyeti (TRY)",
        "Formül Karşılaştırma", "A2:A3", "B1:B3", offset_y=200,
    )],
)
doc1 = build_doc(sheet1, pivots1, next_pivot_id=3)
upsert_dashboard("Formül Karşılaştırma – EVO-RP 210", group, doc1)

# -----------------------------------------------------------------------
# 2. "Satınalma Performansı - ICIS"
#    Pivot (purchase.order.line, rows=partner_id, Areks only - audit
#    tur 4's own hand-verified root cause: the OLD archived company's
#    leftover PO lines also matched the bare x_icis_price>0 domain):
#    avg x_icis_variance_pct -> spills A1:B5 (4 vendors).
#    Chart: bar, reading the pivot's own spilled B column.
# -----------------------------------------------------------------------
pivot3_domain = [["x_icis_price", ">", 0], ["company_id", "=", areks.id]]
pivots2 = {
    "1": {
        "type": "ODOO",
        "id": "1",
        "domain": pivot3_domain,
        "context": {},
        "sortedColumn": None,
        "measures": [
            {"id": "x_icis_variance_pct", "fieldName": "x_icis_variance_pct", "aggregator": "avg"},
            {"id": "__count", "fieldName": "__count", "aggregator": "count"},
        ],
        "model": "purchase.order.line",
        "columns": [],
        "rows": [{"fieldName": "partner_id"}],
        "name": "ICIS Sapma % - Tedarikçi",
        "formulaId": "1",
        "fieldMatching": {},
        "filters": [],
    }
}
sheet2 = new_sheet(
    str(uuid.uuid4()), "Satınalma Performansı",
    [("A1", "=PIVOT(1,20,FALSE,FALSE)")],
    figures=[make_bar_carousel_from_range(
        "Tedarikçi Başına Ortalama ICIS Sapma %",
        "Satınalma Performansı", "A2:A5", "B1:B5", offset_y=200,
    )],
)
doc2 = build_doc(sheet2, pivots2, next_pivot_id=2)
upsert_dashboard("Satınalma Performansı – ICIS", group, doc2)

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: dashboards in group 'Areks Group Demo': "
      f"{Dashboard.search_count([('dashboard_group_id', '=', group.id)])}")
print("=" * 70)
print("11b_spreadsheet_dashboards.py done")
print("=" * 70)
