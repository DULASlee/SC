# P1 file-review (Step 1)

Review date: 2026-10-17. Base: origin/main c193903 (P0 merge).
Source: working-tree semi-finished set backed up 2026-10-17.
Rule: every tighten row must have non-empty test_ref.
Foreign dirs recorded at end, untouched.

## 1. .harness/scripts/validate-task-card.py
- change_kind: 收紧
- rationale: net adds 3 checks (shared-test threshold, dependency graph, registry refs)
- test_ref: test_card_acceptance_integrity.py, test_card_dependency_graph.py, test_card_traceability.py

## 1b. .harness/scripts/validate-task-card.py (loosen part)
- change_kind: 放宽
- rationale: test root allows .harness/tests/ and gate allows harness_tests so harness cards stop using placeholders
- test_ref: test_validate_task_card.py TestHarnessRootsAccepted (4 tests)

## 1c. .harness/scripts/validate-task-card.py (refactor part)
- change_kind: 重构
- rationale: validate_card gains optional repo_root param default None and _load_card_dict helper, CLI exit codes unchanged
- test_ref: test_validate_task_card.py existing 10 tests still pass

## 2. .harness/schema/task-card.schema.json
- change_kind: 新增
- rationale: optional covers/contracts fields with REQ/CTR patterns, required list unchanged so old cards pass
- test_ref: test_card_traceability.py

## 3. .harness/registry/known-shared-tests.yaml
- change_kind: 新增
- rationale: baseline allowlist for pre-TASK-050 placeholder cards, new cards reusing baseline paths still fail
- test_ref: test_card_acceptance_integrity.py

## 4. .harness/registry/contracts.yaml
- change_kind: 新增
- rationale: empty stub items [] so contract-ref check has a registry to read, loader also safe when missing
- test_ref: test_card_traceability.py

## 5. .harness/registry/requirements.yaml
- change_kind: 新增
- rationale: empty stub items [] so requirement-ref check has a registry to read, loader also safe when missing
- test_ref: test_card_traceability.py

## 6. .harness/scripts/gen-task-cards.py
- change_kind: 新增
- rationale: card generator 252 lines, its output must itself pass the validator or it is a bug
- test_ref: test_gen_task_cards.py, test_gen_task_cards_integrity.py

## 7. .harness/tests/test_card_acceptance_integrity.py
- change_kind: 新增
- rationale: 14 tests for allowed roots, sharing threshold, existence checks
- test_ref: self

## 8. .harness/tests/test_card_dependency_graph.py
- change_kind: 新增
- rationale: 11 tests for ring/suspension/coverage violations
- test_ref: self

## 9. .harness/tests/test_card_traceability.py
- change_kind: 新增
- rationale: 13 tests for covers/contracts references
- test_ref: self

## 10. .harness/tests/test_gen_task_cards.py
- change_kind: 新增
- rationale: 6 tests for generator output validity
- test_ref: self

## 11. .harness/tests/test_gen_task_cards_integrity.py
- change_kind: 新增
- rationale: 7 tests for generator allow/deny non-overlap
- test_ref: self

## 12. .harness/tests/test_validate_task_card.py
- change_kind: 新增
- rationale: 4 added tests (harness root accepted, harness gate accepted, wild path rejected, wild gate rejected) on top of untouched dirt, ASCII docstring
- test_ref: self

## Foreign (not adopted, untouched)
- paths: .agents/, .ai-memory/, .desk-switch/, .ecc/, .opencode/, .qoder/, .specstory/, docs/ai-workspace/skills/requirements-analysis/, docs/architecture/*, docs/reports/*, docs/项目harness工程构建/*, fix-skills-drift.bat, skills-lock.json
- change_kind: 新增
- rationale: none of these enter this commit
- test_ref: n/a

## Refill note
- plan file list named only known-shared-tests.yaml
- Step 1 review found contracts.yaml and requirements.yaml companion stubs
- refilled here before commit per plan C4 rule
