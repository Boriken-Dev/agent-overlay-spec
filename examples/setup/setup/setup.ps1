# Writes only into the state directory the consumer provides, never into the overlay root.
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $env:AOS_OVERLAY_STATE | Out-Null
"prepared for $env:AOS_OVERLAY_NAME" | Set-Content -Path (Join-Path $env:AOS_OVERLAY_STATE 'prepared.txt')
Write-Output "setup for $env:AOS_OVERLAY_NAME done"
