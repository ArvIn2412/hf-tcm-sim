$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$out = Join-Path $root 'docs\copyright'
$specPath = Join-Path $out 'DESCRIPTION_CONTENT.json'
$dest = [System.IO.File]::ReadAllText((Join-Path $out 'DESCRIPTION_DOCX_PATH.txt'), [System.Text.Encoding]::UTF8).Trim()
$spec = [System.IO.File]::ReadAllText($specPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$template = $null
$word = $null
$doc = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.ScreenUpdating = $false
    $template = [System.IO.File]::ReadAllText((Join-Path $out 'DESCRIPTION_TEMPLATE_PATH.txt'), [System.Text.Encoding]::UTF8).Trim()
    if (-not (Test-Path -LiteralPath $template)) { throw 'The description DOCX template with five inline figures was not found.' }

    $doc = $word.Documents.Open($template, $false, $false)
    $contents = @($spec | ForEach-Object { $_.text }) -join "`r"
    $body = $doc.Range(0, $doc.Content.End - 1)
    $body.Text = $contents

    $imageCount = 0
    for ($i = 0; $i -lt $spec.Count; $i++) {
        $item = $spec[$i]
        $paragraph = $doc.Paragraphs.Item($i + 1)
        $range = $paragraph.Range
        $format = $paragraph.Range.ParagraphFormat
        $format.Alignment = 0
        $format.FirstLineIndent = 0
        $format.LeftIndent = 0
        $format.RightIndent = 0
        $format.SpaceBefore = 0
        $format.SpaceAfter = 4
        $format.LineSpacingRule = 5
        $format.LineSpacing = 12
        $paragraph.Range.Font.Name = 'Times New Roman'
        $paragraph.Range.Font.Size = 12
        $paragraph.Range.Font.Bold = 0

        switch ($item.kind) {
            'title' {
                $paragraph.Range.ParagraphFormat.Alignment = 1
                $paragraph.Range.Font.Size = 14
                $paragraph.Range.Font.Bold = -1
            }
            'heading' {
                $paragraph.Range.Font.Bold = -1
            }
            'component' {
                $paragraph.Range.Font.Bold = -1
            }
            'authors' {
                $paragraph.Range.Font.Bold = -1
            }
            'image' {
                $paragraph.Range.ParagraphFormat.Alignment = 1
                $paragraph.Range.ParagraphFormat.SpaceBefore = 0
                $paragraph.Range.ParagraphFormat.SpaceAfter = 0
                $markerRange = $paragraph.Range
                $markerRange.End = $markerRange.End - 1
                $markerRange.Text = ''
                $pictureRange = $paragraph.Range
                $pictureRange.Collapse(1)
                $picturePath = Join-Path $root ($item.path -replace '/', '\')
                $picture = $doc.InlineShapes.AddPicture($picturePath, $false, $true, $pictureRange)
                $picture.LockAspectRatio = -1
                $picture.Width = 414
                $imageCount++
            }
        }
    }

    if ($imageCount -ne 5) { throw "Expected five embedded screenshots; inserted $imageCount." }
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Force }
    $doc.SaveAs2($dest, 16)
    $pages = $doc.ComputeStatistics(2)
    $inlineShapes = $doc.InlineShapes.Count
    $preview = Join-Path $out 'description_preview.pdf'
    $doc.ExportAsFixedFormat($preview, 17)
    Write-Output ("DESCRIPTION_DOCX_CREATED pages={0} screenshots={1} bytes={2} pdf_bytes={3}" -f $pages, $inlineShapes, (Get-Item $dest).Length, (Get-Item $preview).Length)
}
finally {
    if ($doc) { $doc.Close(0) }
    if ($word) { $word.Quit() }
}
