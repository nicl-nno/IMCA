# IMCA vs Codebase-Memory disagreement cause analysis

This analysis uses only the 327 comparable unique inputs from the frozen LongMemCode retrieval comparison. The ambiguous repeated `orphans` input is excluded.

## Summary

- Comparable disagreements: 50
- IMCA higher: 41
- Codebase-Memory higher: 9

## IMCA-higher cases

- Cases: 41
- Operations: {'lookup': 1, 'file_symbols': 4, 'callers': 21, 'callees': 12, 'implementors': 1, 'contained_by': 2}
- Anchor types: {'symbol': 30, 'file': 11}
- Codebase-Memory empty result: 10
- Codebase-Memory result contains `unmapped-native`: 10
- Total `unmapped-native` occurrences: 21
- Mean expected targets per case: 4.51
- Mean expected targets found by IMCA: 2.20
- Mean expected targets found by Codebase-Memory: 0.68

## Codebase-Memory-higher cases

- Cases: 9
- Operations: {'file_symbols': 1, 'callers': 8}
- Anchor types: {'file': 7, 'symbol': 2}
- IMCA empty result: 0
- Codebase-Memory result contains `unmapped-native`: 3
- Total `unmapped-native` occurrences: 3
- Mean expected targets per case: 5.00
- Mean expected targets found by IMCA: 1.00
- Mean expected targets found by Codebase-Memory: 2.22

## Detailed IMCA-higher cases

### lookup_method_on_type-027

- Operation: `lookup`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 1
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### cross_module_sibling-003, scope_restricted_lookup-003

- Operation: `file_symbols`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### cross_module_sibling-007, scope_restricted_lookup-007

- Operation: `file_symbols`
- Anchor type: `file`
- IMCA score: 0.8
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 2
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### cross_module_sibling-008

- Operation: `file_symbols`
- Anchor type: `file`
- IMCA score: 1.0
- Codebase-Memory score: 0.6
- Expected targets: 5
- Expected targets found by IMCA: 5
- Expected targets found by Codebase-Memory: 3
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 1

### cross_module_sibling-013

- Operation: `file_symbols`
- Anchor type: `file`
- IMCA score: 0.6
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-002, call_site_enumeration-002

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-003, call_site_enumeration-003

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-006, call_site_enumeration-006

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-008, call_site_enumeration-008

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-009, call_site_enumeration-009

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-011

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.6
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-012

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-014

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-016

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callees_of_symbol-001

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### callees_of_symbol-002

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 4

### callees_of_symbol-005

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.6
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 2
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### callees_of_symbol-006

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 1

### callees_of_symbol-007

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.6
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 2

### callees_of_symbol-008

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.8
- Codebase-Memory score: 0.6
- Expected targets: 5
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 3
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 1

### callees_of_symbol-009

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 3

### callees_of_symbol-010

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 4

### callees_of_symbol-011

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 2

### callees_of_symbol-012

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.8
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 2
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 2

### callees_of_symbol-013

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 1

### callees_of_symbol-017

- Operation: `callees`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 4
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### override_detection-000, trait_implementors-000, plugin_extension_point-000

- Operation: `implementors`
- Anchor type: `symbol`
- IMCA score: 0.6
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 2
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-002

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-003

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-006

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-008

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-009

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.4
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-011

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-014

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.6
- Codebase-Memory score: 0.0
- Expected targets: 5
- Expected targets found by IMCA: 3
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-016

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.4
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 1
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### class_field_invariants-006

- Operation: `contained_by`
- Anchor type: `symbol`
- IMCA score: 0.8
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 2
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### methods_of_class-006

- Operation: `contained_by`
- Anchor type: `symbol`
- IMCA score: 0.6666666666666666
- Codebase-Memory score: 0.5
- Expected targets: 6
- Expected targets found by IMCA: 4
- Expected targets found by Codebase-Memory: 3
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### cross_module_callers-001

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 1
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### cross_module_callers-002

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 1
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: False
- Codebase-Memory unmapped-native count: 0

### cross_module_callers-003

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 1
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

### cross_module_callers-009

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected targets: 1
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 0
- Codebase-Memory empty: True
- Codebase-Memory unmapped-native count: 0

## Detailed Codebase-Memory-higher cases

### cross_module_sibling-029

- Operation: `file_symbols`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 2
- IMCA empty: False
- Codebase-Memory unmapped-native count: 1

### callers_of_symbol-001, call_site_enumeration-001

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.0
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 0
- Expected targets found by Codebase-Memory: 1
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-007, call_site_enumeration-007

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 2
- IMCA empty: False
- Codebase-Memory unmapped-native count: 1

### callers_of_symbol-010, call_site_enumeration-010

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 2
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0

### callers_of_symbol-015

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.4
- Codebase-Memory score: 0.8
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 4
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-001

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.0
- Codebase-Memory score: 0.2
- Expected targets: 5
- Expected targets found by IMCA: 0
- Expected targets found by Codebase-Memory: 1
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-007

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.2
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 2
- IMCA empty: False
- Codebase-Memory unmapped-native count: 1

### multi_hop_impact-010

- Operation: `callers`
- Anchor type: `symbol`
- IMCA score: 0.2
- Codebase-Memory score: 0.4
- Expected targets: 5
- Expected targets found by IMCA: 1
- Expected targets found by Codebase-Memory: 2
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0

### multi_hop_impact-015

- Operation: `callers`
- Anchor type: `file`
- IMCA score: 0.4
- Codebase-Memory score: 0.8
- Expected targets: 5
- Expected targets found by IMCA: 2
- Expected targets found by Codebase-Memory: 4
- IMCA empty: False
- Codebase-Memory unmapped-native count: 0
