param(
    [int]$ServerPort = 18772,
    [int]$BrowserPort = 9241,
    [string]$Output = 'outputs/release_readiness/process_memory.jsonl',
    [string]$StopFile = 'tmp/release-memory.stop'
)
$ErrorActionPreference = 'Stop'
$serverTaskPid = (Get-NetTCPConnection -State Listen -LocalPort $ServerPort | Select-Object -First 1).OwningProcess
$browserTaskPid = (Get-NetTCPConnection -State Listen -LocalPort $BrowserPort | Select-Object -First 1).OwningProcess
$writer = [System.IO.StreamWriter]::new((Join-Path (Get-Location) $Output), $false, [System.Text.UTF8Encoding]::new($false))
try {
    for ($iteration = 0; $iteration -lt 480 -and -not (Test-Path -LiteralPath $StopFile); $iteration++) {
        $inventory = Get-CimInstance Win32_Process
        $descendants = [System.Collections.Generic.HashSet[int]]::new()
        [void]$descendants.Add([int]$browserTaskPid)
        do {
            $added = $false
            foreach ($entry in $inventory) {
                if ($descendants.Contains([int]$entry.ParentProcessId) -and $descendants.Add([int]$entry.ProcessId)) { $added = $true }
            }
        } while ($added)
        $browserProcesses = @($descendants | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        $serverProcess = Get-Process -Id $serverTaskPid
        $row = @{
            timestamp = [DateTime]::UtcNow.ToString('o')
            python_pid = $serverTaskPid
            python_working_set = $serverProcess.WorkingSet64
            python_private = $serverProcess.PrivateMemorySize64
            browser_root_pid = $browserTaskPid
            browser_process_count = $browserProcesses.Count
            browser_working_set_sum = ($browserProcesses | Measure-Object WorkingSet64 -Sum).Sum
            browser_private_sum = ($browserProcesses | Measure-Object PrivateMemorySize64 -Sum).Sum
        }
        $writer.WriteLine(($row | ConvertTo-Json -Compress))
        $writer.Flush()
        Start-Sleep -Milliseconds 500
    }
} finally { $writer.Dispose() }
