param([ValidateSet('audit','file','quick_scan')][string]$Mode='audit')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$result=[ordered]@{}
function Read-Section([string]$Name,[scriptblock]$Probe) {
    try { $result[$Name]=@{ available=$true; data=@(& $Probe) } }
    catch { $result[$Name]=@{ available=$false; error=$_.Exception.GetType().Name } }
}
if ($Mode -eq 'file') {
    Read-Section 'signature' {
        $signature=Get-AuthenticodeSignature -LiteralPath $env:JOJO_INSPECT_FILE
        [pscustomobject]@{Status=[string]$signature.Status;Signer=if($signature.SignerCertificate){$signature.SignerCertificate.Subject}else{''}}
    }
} elseif ($Mode -eq 'quick_scan') {
    # Defender owns detection/remediation policy. JoJo never changes exclusions.
    Start-MpScan -ScanType QuickScan
    $result['scan']=@{available=$true;data=@('Defender quick scan command completed; inspect protection history for findings.')}
} else {
    Read-Section 'defender' { Get-MpComputerStatus | Select-Object AMRunningMode,AntivirusEnabled,RealTimeProtectionEnabled,BehaviorMonitorEnabled,IsTamperProtected,AntivirusSignatureAge,QuickScanAge }
    Read-Section 'threats' { Get-MpThreat | Select-Object ThreatID,ThreatName,IsActive,DidThreatExecute }
    Read-Section 'firewall' { Get-NetFirewallProfile | Select-Object Name,Enabled }
    Read-Section 'antivirus' { Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | Select-Object displayName }
    Read-Section 'startup' {
        Get-CimInstance Win32_StartupCommand | ForEach-Object {
            $command=[string]$_.Command
            [pscustomobject]@{Name=$_.Name;Encoded=($command -match '(?i)(?:powershell|pwsh).*(?:-enc\b|-encodedcommand\b)');TempPath=($command -match '(?i)\\(?:temp|downloads)\\');Bypass=($command -match '(?i)-executionpolicy\s+bypass')}
        }
    }
    Read-Section 'processes' {
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '(?i)(?:powershell|pwsh).*(?:-enc\b|-encodedcommand\b)' } |
            Select-Object Name,ProcessId
    }
    Read-Section 'wifi' {
        # Never request or export Wi-Fi passwords (no key=clear).
        $lines=& netsh.exe wlan show interfaces
        if($LASTEXITCODE -ne 0){throw 'Wi-Fi status unavailable'}
        $lines | Where-Object {$_ -match '^\s*(Authentication|Cipher)\s*:'} | ForEach-Object {$_.Trim()}
    }
}
$result | ConvertTo-Json -Depth 6 -Compress
