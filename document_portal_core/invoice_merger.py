
from typing import List, Dict, Any
from logger import GLOBAL_LOGGER as log

class InvoiceMerger:
    """
    Intelligently merges split invoice pages into a single document record.
    Matches based on:
    1. Exact Invoice Number match.
    2. Exact Total Amount match (heuristic).
    3. Vendor Name match + Close Date.
    """
    
    def merge_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Input: List of extraction results (dict).
        Output: List of merged extraction results.
        """
        merged_docs = []
        
        # Strategy: 
        # 1. Create groups for known Invoice Numbers.
        # 2. Hold "orphans" (no invoice number).
        # 3. Try to attach orphans to groups based on Total Amount.
        
        invoice_groups = {} # Key: InvoiceNum, Value: list of results
        orphans = []
        
        # Pass 1: Group by strong signal (Invoice Details)
        for res in results:
            data = res.get("extracted", {}).get("data", {})
            if not data:
                continue # Skip empty
                
            inv_num = data.get("invoice_details", {}).get("number")
            
            if inv_num:
                key = str(inv_num).strip()
                if key not in invoice_groups:
                    invoice_groups[key] = []
                invoice_groups[key].append(res)
            else:
                orphans.append(res)
                
        # Pass 2: Attach Orphans by Total Amount
        orphan_groups = {} # Key: TotalAmount, Value: list of results
        
        for orphan in orphans:
            data = orphan.get("extracted", {}).get("data", {})
            total = data.get("financials", {}).get("total_amount")
            
            matched = False
            
            # Try to match with existing invoice group
            if total is not None:
                for inv_key, group in invoice_groups.items():
                    master_total = group[0].get("extracted", {}).get("data", {}).get("financials", {}).get("total_amount")
                    if master_total == total:
                        invoice_groups[inv_key].append(orphan)
                        matched = True
                        break
            
            if not matched:
                key = float(total) if total is not None else "unknown"
                if key not in orphan_groups:
                    orphan_groups[key] = []
                orphan_groups[key].append(orphan)
                
        # Pass 3: Attach Shift Reports by Date + Vendor
        shift_groups = {} # Key: (Date, VendorName), Value: list
        final_orphans = []
        
        for orphan in orphan_groups.values():
            for item in orphan:
                data = item.get("extracted", {}).get("data", {})
                doc_type = data.get("doc_type", "").lower() if data.get("doc_type") else ""
                
                shift_details = data.get("shift_report_details", {})
                has_shift_data = any(v is not None for v in shift_details.values())
                
                if "shift" in doc_type or "audit" in doc_type or "report" in doc_type or has_shift_data:
                    vendor_name = data.get("vendor", {}).get("name")
                    inv_date = data.get("invoice_details", {}).get("date")
                    
                    if vendor_name and inv_date:
                        key = (inv_date, vendor_name)
                        if key not in shift_groups:
                            shift_groups[key] = []
                        shift_groups[key].append(item)
                    else:
                        final_orphans.append(item)
                else:
                    final_orphans.append(item)

        # Pass 4: Attach Headerless Shift Pages
        # Scenario A: Exactly one Strong Shift Group
        if len(shift_groups) == 1:
            key = list(shift_groups.keys())[0]
            remaining_orphans = []
            for item in final_orphans:
                 data = item.get("extracted", {}).get("data", {})
                 shift_details = data.get("shift_report_details", {})
                 has_shift_data = any(v is not None for v in shift_details.values())
                 
                 if has_shift_data:
                     shift_groups[key].append(item)
                 else:
                     remaining_orphans.append(item)
            final_orphans = remaining_orphans
            
        # Scenario B: No Strong Group, multiple weak pages
        elif len(shift_groups) == 0:
            potential_shift_pages = []
            remaining_orphans = []
            
            for item in final_orphans:
                 data = item.get("extracted", {}).get("data", {})
                 shift_details = data.get("shift_report_details", {})
                 has_shift_data = any(v is not None for v in shift_details.values())
                 
                 if has_shift_data:
                     potential_shift_pages.append(item)
                 else:
                     remaining_orphans.append(item)
            
            if len(potential_shift_pages) > 1:
                synth_key = ("Unknown Date", "Shift Report")
                shift_groups[synth_key] = potential_shift_pages
                final_orphans = remaining_orphans

        # Collect results
        for group in invoice_groups.values():
            if len(group) > 1:
                merged_docs.append(self._merge_group(group))
            else:
                merged_docs.append(group[0])
                
        for group in shift_groups.values():
             if len(group) > 1:
                merged_docs.append(self._merge_group(group))
             else:
                merged_docs.append(group[0])

        merged_docs.extend(final_orphans)
        return merged_docs

    def _merge_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combines a list of partial invoice results into one master result.
        """
        master = group[0].copy()
        
        # Deep copy data structure to avoid mutation issues
        import copy
        master = copy.deepcopy(group[0])
        master_data = master.get("extracted", {}).get("data", {})
        
        all_line_items = []
        
        for item in group:
            data = item.get("extracted", {}).get("data", {})
            
            # 1. Combine Line Items
            lines = data.get("line_items", [])
            if lines:
                all_line_items.extend(lines)
                
            # 2. Fill Missing Vendor Info
            if not master_data.get("vendor", {}).get("phone") and data.get("vendor", {}).get("phone"):
                 if "vendor" not in master_data: master_data["vendor"] = {}
                 master_data["vendor"]["phone"] = data.get("vendor").get("phone")
            
            # 3. Combine Shift Report Details (Fill Blanks)
            if "shift_report_details" in data:
                if "shift_report_details" not in master_data:
                    master_data["shift_report_details"] = {}
                
                master_details = master_data["shift_report_details"]
                child_details = data["shift_report_details"]
                
                for k, v in child_details.items():
                    if v is not None and master_details.get(k) is None:
                        master_details[k] = v
                 
        # Update Master
        if "line_items" not in master_data:
             master_data["line_items"] = []
        master_data["line_items"] = all_line_items
        
        # Flag as Merged
        master["is_merged"] = True
        master["merged_page_count"] = len(group)
        master["original_filenames"] = [g.get("filename") for g in group]
        
        return master
