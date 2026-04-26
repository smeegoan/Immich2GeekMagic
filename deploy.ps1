param(
    [string]$Tag = "latest"
)

$Registry = "192.168.1.18:5002"
$Image    = "immich2geekmagic"
$Full     = "$Registry/$Image`:$Tag"
$Dir      = $PSScriptRoot

Write-Host "==> Building $Full" -ForegroundColor Cyan
docker build -t $Full $Dir
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }

Write-Host "==> Pushing $Full" -ForegroundColor Cyan
docker push $Full
if ($LASTEXITCODE -ne 0) { Write-Error "Push failed"; exit 1 }

Write-Host ""
Write-Host "Done. Deploy this image in Portainer:" -ForegroundColor Green
Write-Host "  $Full" -ForegroundColor Yellow
