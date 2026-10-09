param([string]$DeviceId = '', [string]$Adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe")
$ErrorActionPreference = 'Stop'
$apk = Join-Path $PSScriptRoot 'app\build\local\JoJo-debug.apk'
if (-not (Test-Path -LiteralPath $Adb)) { throw 'Set -Adb to your Android SDK platform-tools adb.exe.' }
if (-not (Test-Path -LiteralPath $apk)) { throw 'Build the APK with python android/build_local.py first.' }
$devices = @(& $Adb devices | Select-String '^([^\s]+)\s+device$' | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $DeviceId) {
    if ($devices.Count -ne 1) { throw 'Connect and authorize exactly one Android phone, or pass -DeviceId.' }
    $DeviceId = $devices[0]
}
if ($DeviceId -notin $devices) { throw 'Selected phone is not connected and authorized.' }
& $Adb -s $DeviceId install -r $apk
if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
& $Adb -s $DeviceId reverse tcp:8000 tcp:8000
if ($LASTEXITCODE -ne 0) { throw 'USB connection forwarding failed.' }
Write-Output 'Installed. Open JoJo on the phone, enter the laptop pairing key, enable JoJo screen control and microphone, then tap Start listening.'
