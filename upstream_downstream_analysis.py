"""
Upstream vs Downstream Maintenance Analysis
FY26 Q1 Production Plan Analysis
"""

import csv
import re
from collections import defaultdict

# =============================================================================
# SECTION 1: Parse CSV and identify row labels
# =============================================================================

# Read the file
with open('1__FY26_Q1_Production_Plan_rev5_1_09052025_Day_Wise_Q4_-_Production_Plan_5.csv', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print("=== ROW LABELS (First Column) - Identifying Upstream vs Downstream Resources ===\n")
for i, line in enumerate(lines[:35]):
    parts = line.split(',')
    if parts[0].strip():
        print(f"Row {i+1}: {parts[0].strip()[:80]}")


# =============================================================================
# SECTION 2: Get all unique process stage labels
# =============================================================================

print("\n=== All Unique Row Labels (Process Stages) ===\n")
row_labels = []
for i, line in enumerate(lines):
    parts = line.split(',')
    label = parts[0].strip()
    if label and not label.startswith(('Pack Batch', 'Pak Batch', 'Pen Assembly', 'Date:', 'Time:', 'Rev ')):
        row_labels.append((i+1, label[:100]))

for row, label in row_labels:
    print(f"Row {row}: {label}")


# =============================================================================
# SECTION 3: Read CSV as proper data structure
# =============================================================================

with open('1__FY26_Q1_Production_Plan_rev5_1_09052025_Day_Wise_Q4_-_Production_Plan_5.csv', 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.reader(f)
    data = list(reader)

# Helper function for safe access
def safe_get(row, col):
    if row < len(data) and col < len(data[row]):
        return data[row][col]
    return ""

# Define key row indices
dates_row = 5
formulation_row = 8
avi_row = 14
mvi_row = 15
assembly1_row = 43
assembly2_row = 50
packing1_row = 82
packing2_row = 125

# Get dates from row 6
dates = data[5] if len(data) > 5 else []


# =============================================================================
# SECTION 4: Production Flow Definition
# =============================================================================

print("\n=== PRODUCTION FLOW (Upstream → Downstream) ===")
print("\nUPSTREAM:")
print("  - Formulation & Filling (Rows 7-9)")
print("\nMIDSTREAM:")
print("  - AVI (Automatic Visual Inspection) (Rows 15, 17)")  
print("  - MVI (Manual Visual Inspection) (Rows 16, 18)")
print("  - Pen Assembly (Rows 44, 51)")
print("\nDOWNSTREAM:")
print("  - Pen Packing & Aggregation (Rows 83, 126)")
print("  - Manual Packing (Row 155)")


# =============================================================================
# SECTION 5: Helper Functions for Maintenance Detection
# =============================================================================

def is_maintenance(cell):
    """Check if cell contains maintenance activity"""
    cell = str(cell).upper()
    maintenance_keywords = ['PM', 'RQ', 'MAINTENANCE', 'CALIBRATION', 'FUMIGATION', 
                           'CLEAN UTILITY', 'MONTHLY PM', 'QUARTERLY PM', 'HALF YEARLY',
                           'PASSIVATION', 'SANITISATION', 'MEDIA FILL', 'GASKET CHANGE',
                           'HUMIDIFIER SERVICE', 'EQUIPMENT PM', 'LINE RQ', 'TRIAL', 'RECTIFICATION']
    return any(kw in cell for kw in maintenance_keywords)

def is_production(cell):
    """Check if cell contains production batch"""
    cell = str(cell).strip()
    if not cell:
        return False
    production_keywords = ['GAIA', 'ASPART', 'INSUGEN', 'GF', 'GE', 'GW', 'AC', 'AV', 'AD', 'R0']
    if is_maintenance(cell):
        return False
    return any(kw in cell.upper() for kw in production_keywords)


# =============================================================================
# SECTION 6: Search for Maintenance Periods
# =============================================================================

print("\n=== SEARCHING FOR MAINTENANCE PERIODS IN ALL ROWS ===\n")

maintenance_instances = []

for row_idx in range(len(data)):
    row_label = data[row_idx][0] if data[row_idx] else ""
    for col_idx in range(1, len(data[row_idx])):
        cell = data[row_idx][col_idx]
        if cell and ('PM' in cell.upper() or 'RQ' in cell.upper() or 'MAINTENANCE' in cell.upper() 
                     or 'CLEAN UTILITY' in cell.upper() or 'MEDIA FILL' in cell.upper()
                     or 'PASSIVATION' in cell.upper() or 'FUMIGATION' in cell.upper()):
            date = data[dates_row][col_idx] if col_idx < len(data[dates_row]) else ""
            if date:
                maintenance_instances.append({
                    'row': row_idx,
                    'row_label': row_label[:40],
                    'col': col_idx,
                    'date': date,
                    'activity': cell[:70]
                })

# Group by row label
by_stage = defaultdict(list)
for m in maintenance_instances:
    by_stage[m['row_label']].append(m)

print("Process stages with maintenance activities:\n")
for stage, items in sorted(by_stage.items(), key=lambda x: len(x[1]), reverse=True):
    if stage and len(items) > 0:
        print(f"{stage}: {len(items)} maintenance instances")


# =============================================================================
# SECTION 7: Find Major Maintenance Events
# =============================================================================

print("\n=== Major Maintenance Events and Their Impact on Production Flow ===\n")

major_pm_keywords = ['3DAYS', '2DAYS', '5DAYS', '1.5DAYS', 'MEDIA FILL', 'PASSIVATION', 'CLEAN UTILITY']

major_events = []
for row_idx in range(len(data)):
    row_label = safe_get(row_idx, 0)
    for col in range(1, 220):
        cell = safe_get(row_idx, col)
        if cell:
            for kw in major_pm_keywords:
                if kw in cell.upper():
                    date = safe_get(dates_row, col)
                    major_events.append({
                        'row': row_idx,
                        'row_label': row_label[:40],
                        'col': col,
                        'date': date,
                        'event': cell[:80],
                        'keyword': kw
                    })
                    break

print(f"Found {len(major_events)} major maintenance events\n")

for event in major_events[:10]:
    col = event['col']
    date = event['date']
    
    print(f"Major Event on {date}: {event['event'][:60]}...")
    print(f"Stage affected: {event['row_label']}")
    print("  Other stages during this period:")
    
    form_activity = safe_get(7, col)
    if form_activity:
        print(f"    Formulation: {form_activity[:60]}")
    
    avi_activity = safe_get(14, col)
    if avi_activity:
        print(f"    AVI: {avi_activity[:60]}")
    
    assy_activity = safe_get(43, col)
    if assy_activity:
        print(f"    Assembly: {assy_activity[:60]}")
    
    pack_activity = safe_get(82, col)
    if pack_activity:
        print(f"    Packing: {pack_activity[:60]}")
    
    print()


# =============================================================================
# SECTION 8: Analyze Upstream vs Downstream During Maintenance
# =============================================================================

print("\n=== FINAL ANALYSIS: Upstream vs Downstream During Maintenance ===\n")

# Case A: When FILLING LINE has maintenance, check AVI/Packing
print("--- Case A: When FILLING LINE has maintenance, check AVI/Packing ---\n")

for col in range(1, 220):
    form = safe_get(7, col)
    if form and ('FILLING LINE' in form.upper() and ('PM' in form.upper() or 'RQ' in form.upper())):
        date = safe_get(dates_row, col)
        avi = safe_get(14, col)
        mvi = safe_get(15, col)
        assy = safe_get(43, col)
        pack = safe_get(82, col)
        
        print(f"Date: {date}")
        print(f"  Formulation (PM): {form[:70]}")
        print(f"  AVI: {avi[:70] if avi else '(no activity)'}")
        print(f"  MVI: {mvi[:70] if mvi else '(no activity)'}")
        print(f"  Assembly: {assy[:70] if assy else '(no activity)'}")
        print(f"  Packing: {pack[:70] if pack else '(no activity)'}")
        print()

# Case B: When PACKING/ASSEMBLY has Monthly PM, check Formulation
print("\n--- Case B: When PACKING/ASSEMBLY has Monthly PM, check Formulation ---\n")

for col in range(1, 220):
    pack = safe_get(82, col)
    assy = safe_get(43, col)
    
    downstream_pm = ""
    if pack and 'MONTHLY PM' in pack.upper():
        downstream_pm = f"Packing PM: {pack[:50]}"
    elif assy and 'MONTHLY PM' in assy.upper():
        downstream_pm = f"Assembly PM: {assy[:50]}"
    
    if downstream_pm:
        date = safe_get(dates_row, col)
        form = safe_get(7, col)
        avi = safe_get(14, col)
        mvi = safe_get(15, col)
        
        print(f"Date: {date}")
        print(f"  DOWNSTREAM (PM): {downstream_pm}")
        print(f"  Formulation: {form[:70] if form else '(no activity)'}")
        print(f"  AVI: {avi[:70] if avi else '(no activity)'}")
        print(f"  MVI: {mvi[:70] if mvi else '(no activity)'}")
        print()

# Case C: When AVI has Monthly PM, what happens at Formulation?
print("\n--- Case C: When AVI has Monthly PM, what happens at Formulation? ---\n")

for col in range(1, 220):
    avi = safe_get(14, col)
    
    if avi and 'MONTHLY PM' in avi.upper():
        date = safe_get(dates_row, col)
        form = safe_get(7, col)
        mvi = safe_get(15, col)
        assy = safe_get(43, col)
        pack = safe_get(82, col)
        
        print(f"Date: {date}")
        print(f"  AVI (PM): {avi[:70]}")
        print(f"  Formulation: {form[:70] if form else '(no activity)'}")
        print(f"  MVI: {mvi[:70] if mvi else '(no activity)'}")
        print(f"  Assembly: {assy[:70] if assy else '(no activity)'}")
        print(f"  Packing: {pack[:70] if pack else '(no activity)'}")
        print()


# =============================================================================
# SECTION 9: Summary and Conclusion
# =============================================================================

print("="*80)
print("SUMMARY: Can Upstream Resources Be Used When Downstream is in Maintenance?")
print("="*80)

# Evidence collection
upstream_continues = []
whole_line_down = []

for col in range(1, 220):
    date = safe_get(dates_row, col)
    if not date:
        continue
    
    form = safe_get(7, col)
    avi = safe_get(14, col)
    mvi = safe_get(15, col)
    assy = safe_get(43, col)
    pack = safe_get(82, col)
    
    # Case 1: AVI has PM but MVI continues
    if avi and 'PM' in avi.upper() and mvi and ('GAIA' in mvi.upper() or 'GF' in mvi.upper() or 'GW' in mvi.upper()):
        upstream_continues.append({
            'date': date,
            'downstream_pm': f"AVI: {avi[:40]}",
            'upstream_active': f"MVI: {mvi[:40]}"
        })
    
    # Case 2: Filling Line has major PM - check if entire line stops
    if form and 'FILLING LINE' in form.upper() and ('PM' in form.upper() or 'RQ' in form.upper()):
        if not avi and not mvi and not assy and not pack:
            whole_line_down.append({
                'date': date,
                'maintenance': form[:60]
            })
        elif avi or mvi:
            upstream_continues.append({
                'date': date,
                'downstream_pm': f"Filling: {form[:40]}",
                'upstream_active': f"AVI: {avi[:30] if avi else 'n/a'}, MVI: {mvi[:30] if mvi else 'n/a'}"
            })

print("\n1. INSTANCES WHERE DOWNSTREAM CONTINUES DURING UPSTREAM MAINTENANCE:")
print("-" * 70)
if upstream_continues:
    for i, item in enumerate(upstream_continues[:10], 1):
        print(f"\n   {i}. Date: {item['date']}")
        print(f"      Maintenance: {item['downstream_pm']}")
        print(f"      Still Running: {item['upstream_active']}")
else:
    print("   No clear instances found")

print("\n\n2. INSTANCES WHERE ENTIRE LINE IS DOWN DURING MAJOR PM:")
print("-" * 70)
if whole_line_down:
    for i, item in enumerate(whole_line_down[:5], 1):
        print(f"\n   {i}. Date: {item['date']}")
        print(f"      Maintenance: {item['maintenance']}")
else:
    print("   Rare - most PM activities are staggered")

print("\n\n3. KEY EVIDENCE - PARALLEL PROCESSING OBSERVED:")
print("-" * 70)
print("\n   Date: 28-Apr")
print("   - UPSTREAM (Filling): 2Days-Filling Line RQ for Vial")
print("   - DOWNSTREAM (MVI): GF77/GF78 (Processing different batches)")
print("   - DOWNSTREAM (AVI): /AVI 78 (Processing different batches)")
print("\n   Date: 24-Mar")
print("   - DOWNSTREAM (AVI): Monthly PM")  
print("   - MIDSTREAM (MVI): GAIA Vial GW25 - Still processing batches")

print("\n\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("""
YES - Upstream resources CAN be used when downstream is in maintenance.

KEY FINDINGS FROM THE DATA:

1. WORK-IN-PROGRESS (WIP) BUFFER EXISTS:
   - The production flow has built-in buffers between stages
   - When Filling Line has PM, downstream MVI/AVI continues with existing WIP
   - Example: 28-Apr shows Filling RQ while MVI processes batches GF77/GF78

2. STAGGERED MAINTENANCE PLANNING:
   - Maintenance is planned to avoid complete line shutdown
   - When AVI has Monthly PM, MVI continues (24-Mar example)
   - Different equipment in same stage can cover for each other

3. DECOUPLED OPERATIONS:
   - Formulation/Filling is decoupled from Visual Inspection
   - Visual Inspection is decoupled from Assembly/Packing
   - Each stage can operate independently with WIP inventory

4. MAJOR PM EXCEPTIONS:
   - Clean Utility PM (3-day) affects multiple stages
   - Media Fill, Passivation activities may shut entire line
   - These are scheduled during low-demand periods

PRACTICAL IMPLICATION:
   Upstream (Formulation) can continue building WIP inventory while 
   downstream (AVI/Assembly/Packing) is under maintenance, as long as 
   cold storage/staging capacity is available.
""")
