Add-Type -AssemblyName System.Drawing

$src = "C:\Users\anton\claude project\wolman-site\assets\logo-wolman-full.png"
$bmp = [System.Drawing.Bitmap]::FromFile($src)
$w = $bmp.Width
$h = $bmp.Height

$rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
$data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$stride = $data.Stride
$bytes = New-Object byte[] ($stride * $h)
[System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
$bmp.UnlockBits($data)

$strideSample = 3
$rowHasContent = New-Object bool[] $h
for ($y = 0; $y -lt $h; $y += $strideSample) {
    $rowOffset = $y * $stride
    for ($x = 0; $x -lt $w; $x += $strideSample) {
        $px = $rowOffset + $x * 4
        $b = $bytes[$px]; $g = $bytes[$px+1]; $r = $bytes[$px+2]; $a = $bytes[$px+3]
        if ($a -gt 20 -and -not ($r -gt 248 -and $g -gt 248 -and $b -gt 248)) {
            $rowHasContent[$y] = $true
            break
        }
    }
}

# find contiguous row groups
$groups = @()
$inGroup = $false
$startY = 0
for ($y = 0; $y -lt $h; $y++) {
    if ($rowHasContent[$y] -and -not $inGroup) { $inGroup = $true; $startY = $y }
    elseif (-not $rowHasContent[$y] -and $inGroup) {
        $inGroup = $false
        $groups += [PSCustomObject]@{ Start = $startY; End = ($y - 1) }
    }
}
if ($inGroup) { $groups += [PSCustomObject]@{ Start = $startY; End = ($h - 1) } }

# merge groups separated by small gaps (< 15px), keep groups separated by big gaps
$merged = @()
foreach ($grp in $groups) {
    if ($merged.Count -gt 0 -and ($grp.Start - $merged[-1].End) -lt 15) {
        $merged[-1].End = $grp.End
    } else {
        $merged += $grp
    }
}

Write-Output "Row groups found:"
$merged | ForEach-Object { Write-Output ("  y: {0} - {1} (height {2})" -f $_.Start, $_.End, ($_.End - $_.Start)) }

function Get-ColBounds($yStart, $yEnd) {
    $minX = $w; $maxX = 0
    for ($y = $yStart; $y -le $yEnd; $y += $strideSample) {
        $rowOffset = $y * $stride
        for ($x = 0; $x -lt $w; $x += $strideSample) {
            $px = $rowOffset + $x * 4
            $b = $bytes[$px]; $g = $bytes[$px+1]; $r = $bytes[$px+2]; $a = $bytes[$px+3]
            if ($a -gt 20 -and -not ($r -gt 248 -and $g -gt 248 -and $b -gt 248)) {
                if ($x -lt $minX) { $minX = $x }
                if ($x -gt $maxX) { $maxX = $x }
            }
        }
    }
    return [PSCustomObject]@{ MinX = $minX; MaxX = $maxX }
}

$pad = 12
$names = @("icon", "wordmark")
for ($i = 0; $i -lt $merged.Count -and $i -lt 2; $i++) {
    $g = $merged[$i]
    $cb = Get-ColBounds $g.Start $g.End
    $x0 = [Math]::Max(0, $cb.MinX - $pad)
    $y0 = [Math]::Max(0, $g.Start - $pad)
    $cw = [Math]::Min($w - $x0, ($cb.MaxX - $cb.MinX) + $pad * 2)
    $ch = [Math]::Min($h - $y0, ($g.End - $g.Start) + $pad * 2)

    $cropRect = New-Object System.Drawing.Rectangle($x0, $y0, $cw, $ch)
    $cropped = New-Object System.Drawing.Bitmap($cw, $ch)
    $gfx = [System.Drawing.Graphics]::FromImage($cropped)
    $gfx.DrawImage($bmp, (New-Object System.Drawing.Rectangle(0,0,$cw,$ch)), $cropRect, [System.Drawing.GraphicsUnit]::Pixel)
    $gfx.Dispose()

    $outPath = "C:\Users\anton\claude project\wolman-site\assets\logo-$($names[$i]).png"
    $cropped.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropped.Dispose()
    Write-Output ("Saved {0} ({1}x{2})" -f $outPath, $cw, $ch)
}

$bmp.Dispose()
