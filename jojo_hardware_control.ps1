param(
    [ValidateSet("bluetooth", "wifi", "list")][string]$Target = "bluetooth",
    [ValidateSet("status", "on", "off", "toggle")][string]$Action = "status",
    [int]$Value = 50
)
$ErrorActionPreference = "Stop"
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    function Await($Operation, $ResultType) {
        $netTask = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        if (-not $netTask.Wait(4000)) { throw "Radio operation timed out" }
        return $netTask.Result
    }
    [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
    $access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    if ($access -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) {
        throw "Windows denied radio access: $access"
    }
    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    if ($Target -eq "list") {
        foreach ($radio in $radios) { Write-Output "RADIO: $($radio.Name) | $($radio.Kind) | $($radio.State)" }
        exit 0
    }
    $kind = if ($Target -eq "wifi") { "WiFi" } else { "Bluetooth" }
    $matches = @($radios | Where-Object { $_.Kind.ToString() -eq $kind })
    if ($matches.Count -eq 0) { throw "No $kind radio found" }
    foreach ($radio in $matches) {
        if ($Action -eq "status") {
            Write-Output "STATUS: $kind is $($radio.State)"
            continue
        }
        $desired = if ($Action -eq "on") { "On" } elseif ($Action -eq "off") { "Off" } elseif ($radio.State.ToString() -eq "On") { "Off" } else { "On" }
        $state = [Enum]::Parse([Windows.Devices.Radios.RadioState], $desired)
        $result = Await ($radio.SetStateAsync($state)) ([Windows.Devices.Radios.RadioAccessStatus])
        if ($result -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) {
            throw "$kind change denied: $result"
        }
        for ($attempt = 0; $attempt -lt 10 -and $radio.State.ToString() -ne $desired; $attempt++) {
            Start-Sleep -Milliseconds 100
        }
        if ($radio.State.ToString() -ne $desired) { throw "$kind did not reach requested state $desired" }
        Write-Output "SUCCESS: $kind is $desired"
    }
    exit 0
} catch {
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 1
}
