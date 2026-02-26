# Examples: Quality Gate + Test Design (B1 split mode)

## 1) Quality Gate (flat output)
```powershell
$IMAGE="docq:local"
docker run --rm `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  run `
    --paths ./examples/docs `
    --policy-root ./examples/policy/.docq `
    --pbc quality_gate `
    --out-dir ./reports `
    --layout flat
```

Artifacts:
- `reports/qg.summary.json`
- `reports/qg.<path_slug>.report.json`

## 2) Test Design (split by doc_type, flat output)
```powershell
$env:LLMOPS_API_KEY="***"
$IMAGE="docq:local"
docker run --rm `
  -e LLMOPS_API_KEY="$env:LLMOPS_API_KEY" `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  test-design `
    --mode split `
    --split-by doc_type `
    --feature "./examples/docs/features/installment-availability-check.md" `
    --bundle auto `
    --paths ./examples/docs `
    --policy-root ./examples/policy/.docq `
    --pbc test_design `
    --out-dir ./reports `
    --doc-types feature,api,algorithm,service `
    --generators-map "feature=test_design_e2e_v1,api=test_design_api_v1,algorithm=test_design_algorithm_v1,service=test_design_service_v1" `
    --max-input-chars 12000 `
    --max-scenarios 12 `
    --include-negative `
    --include-edge `
    --emit-plan
```

Artifacts (flat):
- `reports/td.<group>.<result_id>.test_suite.json|md`
- `reports/td.<result_id>.coverage.json|md`
- `reports/td.<result_id>.plan.json` (if `--emit-plan`)
