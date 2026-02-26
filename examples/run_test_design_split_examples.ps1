\
param(
  [string]$IMAGE = "docq:local",
  [string]$OUT_DIR = "./reports"
)

if (-not $env:LLMOPS_API_KEY) {
  Write-Error "Set LLMOPS_API_KEY first."
  exit 2
}

docker run --rm `
  -e LLMOPS_API_KEY="$env:LLMOPS_API_KEY" `
  -e LLMOPS_BASE_URL="$env:LLMOPS_BASE_URL" `
  -e LLM_CA_PEM="$env:LLM_CA_PEM" `
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
    --out-dir $OUT_DIR `
    --doc-types feature,api,algorithm,service `
    --generators-map "feature=test_design_e2e_v1,api=test_design_api_v1,algorithm=test_design_algorithm_v1,service=test_design_service_v1" `
    --max-input-chars 12000 `
    --max-scenarios 12 `
    --include-negative `
    --include-edge `
    --emit-plan

Write-Host "Artifacts in: $OUT_DIR"
