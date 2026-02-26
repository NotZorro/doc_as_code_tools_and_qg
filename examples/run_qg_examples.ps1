\
param(
  [string]$IMAGE = "docq:local",
  [string]$OUT_DIR = "./reports"
)

docker run --rm `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  run `
    --paths ./examples/docs `
    --policy-root ./examples/policy/.docq `
    --pbc quality_gate `
    --out-dir $OUT_DIR `
    --layout flat

Write-Host "Artifacts in: $OUT_DIR"
