"""
11b_spreadsheet_dashboards.py
Two LIVE pivot/chart Spreadsheet Dashboards (audit point 9 - replaces
the earlier static-cell draft entirely):

  - "Formül Karşılaştırma - EVO-RP 210": a genuine Odoo pivot
    (model=mrp.production, rows=bom_id) with real measures (kg
    produced, duration, planned qty), rendered via the live =PIVOT(...)
    spill formula (recomputes from real data every time the sheet is
    opened - not a hand-written snapshot), plus a bar chart reading
    from that live range.
  - "Satınalma Performansı - ICIS": a genuine Odoo pivot
    (model=purchase.order.line, rows=partner_id then product_id) with
    the average ICIS variance % measure, same live-pivot mechanism,
    plus a bar chart.

The exact JSON schema for a real Odoo-bound pivot + PIVOT()-spill
formula + chart figure was taken directly from this database's own
working default dashboards (e.g. "Purchase & Vendor analysis", id 187)
and the spreadsheet_dashboard_crm module's own dashboard source file -
not guessed - since getting this JSON wrong produces a silently broken
(blank) dashboard with no Python traceback to debug from.

NOTE (mrp.production has no native "unit cost" field under Standard
costing - cost variance goes to an accounting variance account, not
into a per-MO stored field): the 3rd measure is "product_qty" (planned
qty) instead of a fabricated unit-cost field, which does not exist on
this model. qty_produced + duration are both genuine.

Idempotent: search by dashboard name before create; existing dashboards
are overwritten in place (same id) so the live JSON stays current.

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

rp210 = env['product.template'].sudo().search([('default_code', '=', 'EVO-RP 210')], limit=1)
assert rp210, "EVO-RP 210 not found - run 04_products.py first"


def new_sheet(sheet_id, name, formula_rows, chart_fig=None):
    cells = {}
    for addr, formula in formula_rows:
        cells[addr] = {"content": formula}
    sheet = {
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
        "figures": [chart_fig] if chart_fig else [],
        "tables": [],
        "areGridLinesVisible": True,
        "isVisible": True,
        "headerGroups": [],
        "comments": {},
    }
    return sheet


def build_doc(sheet, pivots):
    return {
        "version": 18,
        "sheets": [sheet],
        "styles": {},
        "formats": {},
        "borders": {},
        "revisionId": str(uuid.uuid4()),
        "uniqueFigureIds": [],
        "settings": {"locale": {"code": "tr_TR", "name": "Turkish"}},
        "pivots": pivots,
        "pivotNextId": 2,
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
        print(f"  [OK] dashboard updated (live pivot refreshed): {name} (id={existing.id})")
        return existing
    dash = Dashboard.create({
        'name': name,
        'dashboard_group_id': group.id,
        'spreadsheet_data': data,
        'is_published': True,
    })
    print(f"  [OK] dashboard created: {name} (id={dash.id})")
    return dash


group = get_or_create_group("Areks Group Demo")

# -----------------------------------------------------------------------
# 1. "Formül Karşılaştırma - EVO-RP 210" - live pivot on mrp.production
# -----------------------------------------------------------------------
pivot1 = {
    "1": {
        "type": "ODOO",
        "domain": [["product_tmpl_id", "=", rp210.id], ["state", "=", "done"]],
        "context": {},
        "sortedColumn": {"measure": "qty_produced:sum", "order": "desc", "domain": []},
        "measures": [
            {"id": "qty_produced:sum", "fieldName": "qty_produced", "aggregator": "sum"},
            {"id": "duration:avg", "fieldName": "duration", "aggregator": "avg"},
            {"id": "product_qty:sum", "fieldName": "product_qty", "aggregator": "sum"},
        ],
        "model": "mrp.production",
        "columns": [],
        "rows": [{"fieldName": "bom_id"}],
        "name": "EVO-RP 210 - Formül Karşılaştırma",
        "formulaId": "1",
        "fieldMatching": {},
    }
}
sheet1 = new_sheet(
    str(uuid.uuid4()), "Formül Karşılaştırma",
    [("A1", "=PIVOT(1,50,FALSE,FALSE)")],
    chart_fig={
        "id": str(uuid.uuid4()),
        "width": 500,
        "height": 300,
        "tag": "chart",
        "col": 0,
        "row": 10,
        "offset": {"x": 0, "y": 0},
        "data": {
            "type": "bar",
            "title": {"text": "EVO-RP 210 - Formül bazında üretilen kg (canlı pivot)", "bold": True},
            "background": "",
            "legendPosition": "top",
            "stacked": False,
            "dataSetsHaveTitle": True,
            "dataSets": [{"dataSetId": "0", "dataRange": "Formül Karşılaştırma!B1:B50"}],
            "labelRange": "Formül Karşılaştırma!A2:A50",
        },
    },
)
doc1 = build_doc(sheet1, pivot1)
upsert_dashboard("Formül Karşılaştırma – EVO-RP 210", group, doc1)

# -----------------------------------------------------------------------
# 2. "Satınalma Performansı - ICIS" - live pivot on purchase.order.line
# -----------------------------------------------------------------------
pivot2 = {
    "1": {
        "type": "ODOO",
        "domain": [["x_icis_price", ">", 0]],
        "context": {},
        "sortedColumn": {"measure": "x_icis_variance_pct:avg", "order": "desc", "domain": []},
        "measures": [
            {"id": "x_icis_variance_pct:avg", "fieldName": "x_icis_variance_pct", "aggregator": "avg"},
            {"id": "__count", "fieldName": "__count", "aggregator": "count"},
        ],
        "model": "purchase.order.line",
        "columns": [],
        "rows": [{"fieldName": "partner_id"}, {"fieldName": "product_id"}],
        "name": "ICIS Sapma % - Tedarikçi / Ürün",
        "formulaId": "1",
        "fieldMatching": {},
    }
}
sheet2 = new_sheet(
    str(uuid.uuid4()), "Satınalma Performansı",
    [("A1", "=PIVOT(1,100,FALSE,FALSE)")],
    chart_fig={
        "id": str(uuid.uuid4()),
        "width": 500,
        "height": 300,
        "tag": "chart",
        "col": 0,
        "row": 15,
        "offset": {"x": 0, "y": 0},
        "data": {
            "type": "bar",
            "title": {"text": "Tedarikçi/Ürün başına ortalama ICIS sapma % (canlı pivot)", "bold": True},
            "background": "",
            "legendPosition": "top",
            "stacked": False,
            "dataSetsHaveTitle": True,
            "dataSets": [{"dataSetId": "0", "dataRange": "Satınalma Performansı!B1:B100"}],
            "labelRange": "Satınalma Performansı!A2:A100",
        },
    },
)
doc2 = build_doc(sheet2, pivot2)
upsert_dashboard("Satınalma Performansı – ICIS", group, doc2)

env.cr.commit()

print("-" * 70)
print(f"SUMMARY: dashboards in group 'Areks Group Demo': "
      f"{Dashboard.search_count([('dashboard_group_id', '=', group.id)])}")
print("=" * 70)
print("11b_spreadsheet_dashboards.py done")
print("=" * 70)
