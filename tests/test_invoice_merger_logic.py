
import pytest
from document_portal_core.invoice_merger import InvoiceMerger

@pytest.fixture
def merger():
    return InvoiceMerger()

def test_merge_by_invoice_number(merger):
    results = [
        # Page 1
        {
            "extracted": {
                "data": {
                    "invoice_details": {"number": "INV-100", "date": "2025-01-01"},
                    "financials": {"total_amount": 100.00},
                    "line_items": [{"description": "Item 1", "total_price": 50.00}]
                },
                "confidence": 90
            }
        },
        # Page 2 (Has Invoice Number)
        {
            "extracted": {
                "data": {
                    "invoice_details": {"number": "INV-100"},
                    "financials": {"total_amount": 100.00},
                    "line_items": [{"description": "Item 2", "total_price": 50.00}]
                },
                "confidence": 95
            }
        }
    ]
    
    merged = merger.merge_results(results)
    assert len(merged) == 1
    data = merged[0]["extracted"]["data"]
    assert data["invoice_details"]["number"] == "INV-100"
    assert len(data["line_items"]) == 2

def test_merge_orphan_by_total(merger):
    results = [
        # Page 1 (Main Header)
        {
            "extracted": {
                "data": {
                    "invoice_details": {"number": "INV-200", "date": "2025-01-01"},
                    "financials": {"total_amount": 55.55},
                },
                "confidence": 90
            }
        },
        # Page 2 (Orphan - No Inv Number, but matches Total)
        {
            "extracted": {
                "data": {
                    "invoice_details": {"number": None},
                    "financials": {"total_amount": 55.55},
                    "line_items": [{"description": "Orphan Item"}]
                },
                "confidence": 80
            }
        }
    ]
    
    merged = merger.merge_results(results)
    assert len(merged) == 1
    assert merged[0]["extracted"]["data"]["invoice_details"]["number"] == "INV-200"
    assert len(merged[0]["extracted"]["data"].get("line_items", [])) == 1

def test_merge_shift_report_by_date_vendor(merger):
    results = [
        # Shift Report Page 1
        {
            "extracted": {
                "data": {
                    "doc_type": "Shift Report",
                    "vendor": {"name": "Test Vendor"},
                    "invoice_details": {"date": "2025-01-01"},
                    "shift_report_details": {"total_sales": 500}
                },
                "confidence": 90
            }
        },
        # Shift Report Page 2
        {
            "extracted": {
                "data": {
                    "doc_type": "Shift Report",
                    "vendor": {"name": "Test Vendor"},
                    "invoice_details": {"date": "2025-01-01"},
                    "shift_report_details": {"fuel_sales": 200}
                },
                "confidence": 90
            }
        }
    ]
    
    merged = merger.merge_results(results)
    assert len(merged) == 1
    data = merged[0]["extracted"]["data"]
    assert data["vendor"]["name"] == "Test Vendor"
    assert data["shift_report_details"]["total_sales"] == 500
    assert data["shift_report_details"]["fuel_sales"] == 200

def test_merge_headerless_shift_report(merger):
    # Tests the fallback logic "Scenario A/B"
    results = [
        # Strong Header
        {
            "extracted": {
                "data": {
                    "doc_type": "Shift Report",
                    "vendor": {"name": "Test Vendor"},
                    "invoice_details": {"date": "2025-01-01"},
                    "shift_report_details": {"total_sales": 100}
                }
            }
        },
        # Weak Page (No Header, but has shift data)
        {
            "extracted": {
                "data": {
                    "doc_type": "Other",
                    "shift_report_details": {"fuel_sales": 50}
                }
            }
        }
    ]
    
    merged = merger.merge_results(results)
    assert len(merged) == 1
    assert merged[0]["extracted"]["data"]["shift_report_details"]["fuel_sales"] == 50
