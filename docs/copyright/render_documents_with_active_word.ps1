$ErrorActionPreference = 'Stop'
$out = $PSScriptRoot
$pathFiles = @('DESCRIPTION_DOCX_PATH.txt', 'SOURCE_CODE_DOCX_PATH.txt')
$word = [System.Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
$oldScreenUpdating = $word.ScreenUpdating
$word.ScreenUpdating = $false
try {
    foreach ($name in $pathFiles) {
        $path = [System.IO.File]::ReadAllText((Join-Path $out $name), [System.Text.Encoding]::UTF8).Trim()
        $doc = $null
        try {
            $doc = $word.Documents.Open($path, $false, $true)
            $pages = $doc.ComputeStatistics(2)
            $paragraphs = $doc.Paragraphs.Count
            $images = $doc.InlineShapes.Count
            $pdfName = if ($name.StartsWith('DESCRIPTION')) { 'description_preview.pdf' } else { 'source_code_preview.pdf' }
            $pdf = Join-Path $out $pdfName
            $doc.ExportAsFixedFormat($pdf, 17)
            Write-Output ("DOCX_OK name={0} pages={1} paragraphs={2} images={3} pdf_bytes={4}" -f $name, $pages, $paragraphs, $images, (Get-Item $pdf).Length)
        }
        finally {
            if ($doc) { $doc.Close(0) }
        }
    }
}
finally {
    $word.ScreenUpdating = $oldScreenUpdating
}
