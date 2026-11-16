$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'source_word_probe.log'
[System.IO.File]::WriteAllText($out, "START $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
$path = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot 'SOURCE_CODE_DOCX_PATH.txt'), [System.Text.Encoding]::UTF8).Trim()
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    [System.IO.File]::AppendAllText($out, "WORD_CREATED $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
    $doc = $word.Documents.Open($path, $false, $true)
    [System.IO.File]::AppendAllText($out, "OPENED $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
    $paragraphs = $doc.Paragraphs.Count
    [System.IO.File]::AppendAllText($out, "PARAGRAPHS=$paragraphs $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
    $pages = $doc.ComputeStatistics(2)
    [System.IO.File]::AppendAllText($out, "PAGES=$pages $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
    $doc.ExportAsFixedFormat((Join-Path $PSScriptRoot 'source_code_preview.pdf'), 17)
    [System.IO.File]::AppendAllText($out, "PDF_EXPORTED $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
}
finally {
    if ($doc) { $doc.Close(0) }
    if ($word) { $word.Quit() }
    [System.IO.File]::AppendAllText($out, "CLOSED $(Get-Date -Format o)`r`n", [System.Text.Encoding]::UTF8)
}
