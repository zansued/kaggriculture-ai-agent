# Extract GitHub token from Windows Credential Manager (CredRead) and push.
Add-Type -Namespace Win32 -Name CredUtil -MemberDefinition @'
[DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
public static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);
[DllImport("advapi32.dll", SetLastError = true)]
public static extern void CredFree(IntPtr cred);
'@

function Get-CredentialPassword {
    param([string]$Target)
    $ptr = [IntPtr]::Zero
    if (-not [Win32.CredUtil]::CredRead($Target, 1, 0, [ref]$ptr)) {
        return $null
    }
    try {
        $blobSize = [System.Runtime.InteropServices.Marshal]::ReadInt32($ptr, 32)
        $blobPtr  = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($ptr, 40)
        if ($blobSize -le 0) { return $null }
        $bytes = New-Object byte[] $blobSize
        [System.Runtime.InteropServices.Marshal]::Copy($blobPtr, $bytes, 0, $blobSize)
        return [System.Text.Encoding]::Unicode.GetString($bytes)
    } finally {
        [Win32.CredUtil]::CredFree($ptr)
    }
}

# Try the stored credential targets in order.
$targets = @(
    "git:https://x-access-token@github.com",
    "git:https://zansued@github.com",
    "git:https://github.com"
)
$token = $null
foreach ($t in $targets) {
    $pw = Get-CredentialPassword -Target $t
    if ($pw -and $pw.Length -gt 10) {
        Write-Output "using credential: $t (len=$($pw.Length))"
        $token = $pw
        break
    }
}

if (-not $token) {
    Write-Output "NO_TOKEN_FOUND"
    exit 1
}

$pushUrl = "https://x-access-token:$token@github.com/zansued/kaggriculture-ai-agent.git"
git push $pushUrl main 2>&1 | Select-Object -Last 6
Write-Output "PUSH_EXIT=$LASTEXITCODE"
exit $LASTEXITCODE
