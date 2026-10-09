# Copied outside the installation before launch. This script is never run by tests.
param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$report = Join-Path $PSScriptRoot 'result.txt'
function Assert-PlainTree([string]$target) {
    $item = Get-Item -LiteralPath $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked directories/files must be removed from the installation before uninstall.' }
    if ($item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $target -Force) { Assert-PlainTree $child.FullName }
    }
}
try {
    $plan = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'plan.json') -Raw | ConvertFrom-Json
    $targetRoot = [IO.Path]::GetFullPath([string]$plan.root).TrimEnd('\')
    $resolved = (Resolve-Path -LiteralPath $targetRoot).ProviderPath.TrimEnd('\')
    if ($targetRoot -ne $resolved -or $targetRoot -eq [IO.Path]::GetPathRoot($targetRoot).TrimEnd('\') -or $targetRoot -eq $env:USERPROFILE) { throw 'Unsafe installation root.' }
    foreach ($marker in @('jojo_core.py','jojo_desktop.py','jojo_start.py','jojo_uninstall.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetRoot $marker) -PathType Leaf)) { throw 'JoJo install marker missing.' }
    }
    # Validate every recursive deletion target and reject reparse points BEFORE deleting.
    Assert-PlainTree $targetRoot
    $userData = [IO.Path]::GetFullPath([string]$plan.data_dir).TrimEnd('\')
    $standardData = (Join-Path $env:LOCALAPPDATA 'JoJo').TrimEnd('\')
    if ($userData -ne $targetRoot -and -not $userData.StartsWith($targetRoot + '\', [StringComparison]::OrdinalIgnoreCase) -and $userData -ne $standardData) { throw 'Unapproved external user data directory.' }
    if (Test-Path -LiteralPath $userData) { Assert-PlainTree $userData }
    $startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\jojo_autostart.vbs'
    if ([IO.Path]::GetFullPath([string]$plan.startup) -ne $startup) { throw 'Startup path mismatch.' }
    if (Test-Path -LiteralPath $startup) {
        Assert-PlainTree $startup
        $startupRoot = '(?im)^\s*\w+\.CurrentDirectory\s*=\s*"' + [regex]::Escape($targetRoot) + '"\s*$'
        if ((Get-Content -LiteralPath $startup -Raw) -notmatch $startupRoot) { throw 'Startup entry belongs to another installation.' }
    }
    if ($ValidateOnly) { Write-Output ('Validated uninstall target: ' + $targetRoot); exit 0 }
    Start-Sleep -Seconds 3
    # Only JoJo Python entrypoints in this exact installation; never all Python processes.
    $entries = @('jojo_core.py','jojo_desktop.py','jojo_screen_overlay.py','jojo_overlay.py')
    $pythonProcesses = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' })
    foreach ($proc in $pythonProcesses) {
        foreach ($entry in $entries) {
            $relative = '(?:^|\s|"|'')' + [regex]::Escape($entry) + '(?:\s|"|''|$)'
            if ($proc.CommandLine -match $relative) { throw 'A JoJo process was launched with a relative path. Stop it manually before uninstall; its installation cannot be verified safely.' }
        }
    }
    foreach ($proc in $pythonProcesses) {
        if ($proc.Name -notmatch '^pythonw?\.exe$') { continue }
        foreach ($entry in $entries) {
            $expression = '(?:^|\s|"|'')' + [regex]::Escape((Join-Path $targetRoot $entry)) + '(?:\s|"|''|$)'
            if ($proc.CommandLine -match $expression) { Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop; break }
        }
    }
    if (Test-Path -LiteralPath $startup) { Remove-Item -LiteralPath $startup -Force }
    if ($plan.erase_cloud) {
        $cloud = Join-Path $targetRoot 'jojo_uninstall_cloud.py'
        & ([string]$plan.python) $cloud --confirmed-erase-jojo *> (Join-Path $PSScriptRoot 'cloud-result.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Cloud deletion failed or is incomplete. Local installation kept for retry. Startup is disabled. See cloud-result.txt.' }
    }
    # Recheck exact resolved path and links immediately before recursive removal.
    if ((Resolve-Path -LiteralPath $targetRoot).ProviderPath.TrimEnd('\') -ne $targetRoot) { throw 'Install path changed.' }
    Assert-PlainTree $targetRoot
    Remove-Item -LiteralPath $targetRoot -Recurse -Force
    if ($userData -eq $standardData -and (Test-Path -LiteralPath $userData)) {
        if ((Resolve-Path -LiteralPath $userData).ProviderPath.TrimEnd('\') -ne $standardData) { throw 'User data path changed.' }
        Assert-PlainTree $userData
        Remove-Item -LiteralPath $userData -Recurse -Force
    }
    if (Test-Path -LiteralPath $targetRoot) { throw 'Some install files remain.' }
    $message = 'JoJo laptop installation and startup entry removed. Uninstall Android separately on the phone. Other backups/downloads and OS history are not erased. A temporary helper/report remains at: ' + $PSScriptRoot
    if (-not $plan.erase_cloud) { $message += ' Firestore data was retained.' }
    Set-Content -LiteralPath $report -Value $message
} catch {
    if ($ValidateOnly) { Write-Error $_; exit 1 }
    $message = 'JoJo uninstall incomplete: ' + $_.Exception.Message + ' Report: ' + $report
    Set-Content -LiteralPath $report -Value $message
}
try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($message, 'JoJo uninstall result') | Out-Null } catch {}
