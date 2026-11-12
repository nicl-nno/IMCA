# IMCA vs Codebase-Memory retrieval disagreements

This analysis reuses the frozen retrieval predictions from the existing LongMemCode comparison and does not rerun either memory system.

The original benchmark-level results are reported separately from the unique-input analysis. Repeated inputs with different expected answers are treated as ambiguous groups rather than independent comparable inputs.

## Task-level results

- Tasks: 425
- IMCA higher score: 54
- Codebase-Memory higher score: 12
- Equal score: 359

- Only IMCA full score: 11
- Only Codebase-Memory full score: 0
- Both full score: 261
- Neither full score: 153

## Unique-input audit

- Distinct query + question inputs: 328
- Comparable unique inputs: 327
- Ambiguous expected groups: 1

An ambiguous expected group contains the same retrieval input more than once with different benchmark expected answers. Such a group is preserved for auditing but excluded from the main unique-input direction counts.

## Comparable unique-input results

- IMCA higher score: 41
- Codebase-Memory higher score: 9
- Equal score: 277

- Only IMCA full score: 7
- Only Codebase-Memory full score: 0
- Both full score: 202
- Neither full score: 118

## Unique inputs where IMCA scores higher

- Operations: callers: 21, callees: 12, file_symbols: 4, contained_by: 2, implementors: 1, lookup: 1

- `lookup_method_on_type-027` — `lookup` — Agent calling method `FastAPI#redoc_html` on its type. Operation: lookup; bare name: true; name: FastAPI#redoc_html
- `cross_module_sibling-003, scope_restricted_lookup-003` — `file_symbols` — Agent discovering siblings in `applications.py`. Operation: file_symbols; file path: applications.py
- `cross_module_sibling-007, scope_restricted_lookup-007` — `file_symbols` — Agent discovering siblings in `datastructures.py`. Operation: file_symbols; file path: datastructures.py
- `cross_module_sibling-008` — `file_symbols` — Agent discovering siblings in `encoders.py`. Operation: file_symbols; file path: encoders.py
- `cross_module_sibling-013` — `file_symbols` — Agent discovering siblings in `params.py`. Operation: file_symbols; file path: params.py
- `callers_of_symbol-002, call_site_enumeration-002` — `callers` — Bug suspected in `Depends` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.params`/Depends#
- `callers_of_symbol-003, call_site_enumeration-003` — `callers` — Bug suspected in `APIRoute` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRoute#
- `callers_of_symbol-006, call_site_enumeration-006` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:applications.py
- `callers_of_symbol-008, call_site_enumeration-008` — `callers` — Bug suspected in `Default` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.datastructures`/Default().
- `callers_of_symbol-009, call_site_enumeration-009` — `callers` — Bug suspected in `generate_unique_id` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.utils`/generate_unique_id().
- `callers_of_symbol-011` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:params.py
- `callers_of_symbol-012` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:exceptions.py
- `callers_of_symbol-014` — `callers` — Bug suspected in `Example` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.openapi.models`/Example#
- `callers_of_symbol-016` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:security/oauth2.py
- `callees_of_symbol-001` — `callees` — Bug downstream of `app` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.routing`/get_request_handler().app().
- `callees_of_symbol-002` — `callees` — Bug downstream of `get_openapi_path` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.openapi.utils`/get_openapi_path().
- `callees_of_symbol-005` — `callees` — Bug downstream of `get_dependant` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.dependencies.utils`/get_dependant().
- `callees_of_symbol-006` — `callees` — Bug downstream of `APIRouter#include_router` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.routing`/APIRouter#include_router().
- `callees_of_symbol-007` — `callees` — Bug downstream of `_get_openapi_operation_parameters` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.openapi.utils`/_get_openapi_operation_parameters().
- `callees_of_symbol-008` — `callees` — Bug downstream of `APIWebSocketRoute#__init__` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.routing`/APIWebSocketRoute#__init__().
- `callees_of_symbol-009` — `callees` — Bug downstream of `_extract_form_body` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.dependencies.utils`/_extract_form_body().
- `callees_of_symbol-010` — `callees` — Bug downstream of `get_openapi` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.openapi.utils`/get_openapi().
- `callees_of_symbol-011` — `callees` — Bug downstream of `request_body_to_args` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.dependencies.utils`/request_body_to_args().
- `callees_of_symbol-012` — `callees` — Bug downstream of `FastAPI#__init__` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.applications`/FastAPI#__init__().
- `callees_of_symbol-013` — `callees` — Bug downstream of `request_params_to_args` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.dependencies.utils`/request_params_to_args().
- `callees_of_symbol-017` — `callees` — Bug downstream of `FastAPI#setup` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.applications`/FastAPI#setup().
- `override_detection-000, trait_implementors-000, plugin_extension_point-000` — `implementors` — Agent refactoring `BaseModelWithConfig` — find every override. Operation: implementors; sym stable id: fastapi `fastapi.openapi.models`/BaseModelWithConfig#
- `multi_hop_impact-002` — `callers` — Multi-hop impact starting from `Depends` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.params`/Depends#
- `multi_hop_impact-003` — `callers` — Multi-hop impact starting from `APIRoute` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRoute#
- `multi_hop_impact-006` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:applications.py
- `multi_hop_impact-008` — `callers` — Multi-hop impact starting from `Default` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.datastructures`/Default().
- `multi_hop_impact-009` — `callers` — Multi-hop impact starting from `generate_unique_id` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.utils`/generate_unique_id().
- `multi_hop_impact-011` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:params.py
- `multi_hop_impact-014` — `callers` — Multi-hop impact starting from `Example` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.openapi.models`/Example#
- `multi_hop_impact-016` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:security/oauth2.py
- `class_field_invariants-006` — `contained_by` — Agent understanding invariants of `UploadFile` — members. Operation: contained_by; sym stable id: fastapi `fastapi.datastructures`/UploadFile#
- `methods_of_class-006` — `contained_by` — Rename audit on `UploadFile` — every method. Operation: contained_by; sym stable id: fastapi `fastapi.datastructures`/UploadFile#
- `cross_module_callers-001` — `callers` — Cross-module callers of `APIRouter#on_event`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#on_event().
- `cross_module_callers-002` — `callers` — Cross-module callers of `get_swagger_ui_oauth2_redirect_html`. Operation: callers; sym stable id: fastapi `fastapi.openapi.docs`/get_swagger_ui_oauth2_redirect_html().
- `cross_module_callers-003` — `callers` — Cross-module callers of `APIRouter#get`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#get().
- `cross_module_callers-009` — `callers` — Cross-module callers of `APIRouter#include_router`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#include_router().

## Unique inputs where Codebase-Memory scores higher

- Operations: callers: 8, file_symbols: 1

- `cross_module_sibling-029` — `file_symbols` — Agent discovering siblings in `dependencies/utils.py`. Operation: file_symbols; file path: dependencies/utils.py
- `callers_of_symbol-001, call_site_enumeration-001` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:openapi/models.py
- `callers_of_symbol-007, call_site_enumeration-007` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:dependencies/utils.py
- `callers_of_symbol-010, call_site_enumeration-010` — `callers` — Bug suspected in `BaseModelWithConfig` — enumerate callers. Operation: callers; sym stable id: fastapi `fastapi.openapi.models`/BaseModelWithConfig#
- `callers_of_symbol-015` — `callers` — Bug suspected in `py` — enumerate callers. Operation: callers; sym stable id: file:security/http.py
- `multi_hop_impact-001` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:openapi/models.py
- `multi_hop_impact-007` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:dependencies/utils.py
- `multi_hop_impact-010` — `callers` — Multi-hop impact starting from `BaseModelWithConfig` (depth-1 approximation). Operation: callers; sym stable id: fastapi `fastapi.openapi.models`/BaseModelWithConfig#
- `multi_hop_impact-015` — `callers` — Multi-hop impact starting from `py` (depth-1 approximation). Operation: callers; sym stable id: file:security/http.py

## Strict full-score disagreements

- Comparable unique inputs with only IMCA full score: 7
- Comparable unique inputs with only Codebase-Memory full score: 0

### Only IMCA

#### lookup_method_on_type-027

- Operation: `lookup`
- Query: Agent calling method `FastAPI#redoc_html` on its type. Operation: lookup; bare name: true; name: FastAPI#redoc_html
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#redoc_html().']}`
- IMCA: `['fastapi `fastapi.applications`/FastAPI#redoc_html().']`
- Codebase-Memory: `[]`

#### cross_module_sibling-008

- Operation: `file_symbols`
- Query: Agent discovering siblings in `encoders.py`. Operation: file_symbols; file path: encoders.py
- IMCA score: 1.0
- Codebase-Memory score: 0.6
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.encoders`/jsonable_encoder().', 'file:encoders.py', 'fastapi `fastapi.encoders`/generate_encoders_by_class_tuples().', 'fastapi `fastapi.encoders`/decimal_encoder().', 'fastapi `fastapi.encoders`/isoformat().']}`
- IMCA: `['fastapi `fastapi.encoders`/jsonable_encoder().', 'file:encoders.py', 'fastapi `fastapi.encoders`/generate_encoders_by_class_tuples().', 'fastapi `fastapi.encoders`/isoformat().', 'fastapi `fastapi.encoders`/decimal_encoder().']`
- Codebase-Memory: `['unmapped-native:longmemcode-source.fastapi.encoders.ENCODERS_BY_TYPE', 'fastapi `fastapi.encoders`/decimal_encoder().', 'fastapi `fastapi.encoders`/encoders_by_class_tuples.', 'fastapi `fastapi.encoders`/generate_encoders_by_class_tuples().', 'fastapi `fastapi.encoders`/isoformat().']`

#### callees_of_symbol-017

- Operation: `callees`
- Query: Bug downstream of `FastAPI#setup` — enumerate callees. Operation: callees; sym stable id: fastapi `fastapi.applications`/FastAPI#setup().
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#redoc_html().', 'fastapi `fastapi.applications`/FastAPI#openapi().', 'fastapi `fastapi.applications`/FastAPI#swagger_ui_html().', 'fastapi `fastapi.applications`/FastAPI#swagger_ui_redirect().']}`
- IMCA: `['fastapi `fastapi.applications`/FastAPI#openapi().', 'fastapi `fastapi.applications`/FastAPI#swagger_ui_html().', 'fastapi `fastapi.applications`/FastAPI#swagger_ui_redirect().', 'fastapi `fastapi.applications`/FastAPI#redoc_html().']`
- Codebase-Memory: `[]`

#### cross_module_callers-001

- Operation: `callers`
- Query: Cross-module callers of `APIRouter#on_event`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#on_event().
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#on_event().']}`
- IMCA: `['fastapi `fastapi.applications`/FastAPI#on_event().']`
- Codebase-Memory: `[]`

#### cross_module_callers-002

- Operation: `callers`
- Query: Cross-module callers of `get_swagger_ui_oauth2_redirect_html`. Operation: callers; sym stable id: fastapi `fastapi.openapi.docs`/get_swagger_ui_oauth2_redirect_html().
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#swagger_ui_redirect().']}`
- IMCA: `['file:applications.py', 'fastapi `fastapi.applications`/FastAPI#swagger_ui_redirect().']`
- Codebase-Memory: `['file:applications.py']`

#### cross_module_callers-003

- Operation: `callers`
- Query: Cross-module callers of `APIRouter#get`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#get().
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#get().']}`
- IMCA: `['fastapi `fastapi.applications`/FastAPI#get().']`
- Codebase-Memory: `[]`

#### cross_module_callers-009

- Operation: `callers`
- Query: Cross-module callers of `APIRouter#include_router`. Operation: callers; sym stable id: fastapi `fastapi.routing`/APIRouter#include_router().
- IMCA score: 1.0
- Codebase-Memory score: 0.0
- Expected: `{'kind': 'contains', 'required': ['fastapi `fastapi.applications`/FastAPI#include_router().']}`
- IMCA: `['fastapi `fastapi.applications`/FastAPI#include_router().']`
- Codebase-Memory: `[]`

### Only Codebase-Memory

No comparable unique input gives Codebase-Memory a full score while IMCA does not receive a full score.

## Ambiguous expected groups

### orphans — dead_export_detection-000, dead_export_detection-001, dead_export_detection-002, dead_export_detection-003, dead_export_detection-004, dead_export_detection-005, dead_export_detection-006, dead_export_detection-007, dead_export_detection-008, dead_export_detection-009, dead_export_detection-010

- Query: Agent cleaning dead exports — symbol has no callers. Operation: orphans; kind: function
- Number of tasks: 11
- Distinct expected answers: 11
- Directions observed: equal, imca_higher
- Full-score statuses observed: neither_pass, only_imca

- `dead_export_detection-000`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.openapi.models`/EmailStr#__get_pydantic_core_schema__().']}`
- `dead_export_detection-001`: IMCA=1.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.param_functions`/Header().']}`
- `dead_export_detection-002`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.routing`/APIRouter#route().']}`
- `dead_export_detection-003`: IMCA=1.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.param_functions`/File().']}`
- `dead_export_detection-004`: IMCA=1.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.param_functions`/Cookie().']}`
- `dead_export_detection-005`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.cli`/main().']}`
- `dead_export_detection-006`: IMCA=1.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.param_functions`/Query().']}`
- `dead_export_detection-007`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.openapi.utils`/generate_operation_id().']}`
- `dead_export_detection-008`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.encoders`/generate_encoders_by_class_tuples().']}`
- `dead_export_detection-009`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.openapi.models`/EmailStr#__get_pydantic_json_schema__().']}`
- `dead_export_detection-010`: IMCA=0.0, Codebase-Memory=0.0, expected=`{'kind': 'contains', 'required': ['fastapi `fastapi.param_functions`/Depends().']}`

## Interpretation status

The script reports disagreement cases without assigning causal labels. The causes should be determined by manual inspection and quantitative analysis of representative comparable inputs.
