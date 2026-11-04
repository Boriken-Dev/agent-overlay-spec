# Writes only into the state directory the consumer provides, never into the overlay root.
# The first argument, also in AOS_SETUP_PHASE, is the phase: install, sync or remove.
param([string]$Phase = '')
$ErrorActionPreference = 'Stop'
switch ($Phase) {
    { $_ -in 'install', 'sync' } {
        New-Item -ItemType Directory -Force -Path $env:AOS_OVERLAY_STATE | Out-Null
        "prepared for $env:AOS_OVERLAY_NAME" | Set-Content -Path (Join-Path $env:AOS_OVERLAY_STATE 'prepared.txt')
        Write-Output "setup ($Phase) for $env:AOS_OVERLAY_NAME done"
    }
    'remove' { Write-Output "nothing to undo for $env:AOS_OVERLAY_NAME" }
    default { }  # a phase this script does not know: nothing to do
}
