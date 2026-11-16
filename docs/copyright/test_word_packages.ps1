$ErrorActionPreference = 'Continue'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$template = Join-Path $root 'Опис_NIDS-Core.docx'
$tests = @(
    $template,
    (Join-Path $PSScriptRoot 'debug\roundtrip_xml.docx'),
    (Join-Path $PSScriptRoot 'debug\media_only.docx'),
    (Join-Path $PSScriptRoot 'debug\xml_only.docx'),
    [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot 'DESCRIPTION_DOCX_PATH.txt'), [System.Text.Encoding]::UTF8).Trim()
)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
foreach ($path in $tests) {
    try {
        $doc = $word.Documents.Open($path, $false, $true)
        Write-Output ("OPEN_OK {0} pages={1} images={2}" -f (Split-Path $path -Leaf), $doc.ComputeStatistics(2), $doc.InlineShapes.Count)
        $doc.Close(0)
    }
    catch {
        Write-Output ("OPEN_FAIL {0} {1}" -f (Split-Path $path -Leaf), $_.Exception.Message)
    }
}
$word.Quit()
