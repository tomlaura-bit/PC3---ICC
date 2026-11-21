$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$evidenceDir = Join-Path $projectRoot "evidence"
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "us-east-1"
$endpoint = "http://localhost:4566"

docker compose -f (Join-Path $projectRoot "docker-compose.yml") ps --format json |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "docker-compose.json")

aws dynamodb list-tables --endpoint-url $endpoint --output json |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "dynamodb-tables.json")

aws dynamodb scan --table-name pc3-orders --select COUNT --endpoint-url $endpoint --output json |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "dynamodb-orders-count.json")

aws s3api list-objects-v2 --bucket pc3-user-images --endpoint-url $endpoint --output json |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "s3-user-images.json")

$queueUrl = aws sqs get-queue-url --queue-name pc3-orders-queue --endpoint-url $endpoint --query QueueUrl --output text
aws sqs get-queue-attributes --queue-url $queueUrl --attribute-names All --endpoint-url $endpoint --output json |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "sqs-queue.json")

Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Depth 8 |
  Set-Content -Encoding utf8 (Join-Path $evidenceDir "application-health.json")

Write-Output "Evidencias guardadas en $evidenceDir"
