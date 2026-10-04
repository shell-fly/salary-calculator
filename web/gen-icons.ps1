# web/gen-icons.ps1 — programmatically render the app icon at multiple sizes using GDI+.
# No external assets or network needed. Run:  powershell -ExecutionPolicy Bypass -File web/gen-icons.ps1
Add-Type -AssemblyName System.Drawing

$outDir = Join-Path $PSScriptRoot 'icons'
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

function Draw-Icon {
    param([int]$Size, [switch]$Maskable)
    $bmp = New-Object System.Drawing.Bitmap($Size, $Size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.Clear([System.Drawing.Color]::Transparent)

    # Background: rounded square (or full-bleed for maskable) with green->teal gradient
    $rect = New-Object System.Drawing.RectangleF(0, 0, $Size, $Size)
    if ($Maskable) {
        $path = New-Object System.Drawing.Drawing2D.GraphicsPath
        $path.AddRectangle($rect)
    } else {
        $r = [single]($Size * 0.22)
        $d = $r * 2
        $path = New-Object System.Drawing.Drawing2D.GraphicsPath
        $path.AddArc(0, 0, $d, $d, 180, 90)
        $path.AddArc($Size-$d, 0, $d, $d, 270, 90)
        $path.AddArc($Size-$d, $Size-$d, $d, $d, 0, 90)
        $path.AddArc(0, $Size-$d, $d, $d, 90, 90)
        $path.CloseFigure()
    }
    $c1 = [System.Drawing.Color]::FromArgb(255, 34, 160, 110)   # green
    $c2 = [System.Drawing.Color]::FromArgb(255, 16, 130, 150)   # teal
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $c1, $c2, 45)
    $g.FillPath($brush, $path)

    # Calculator body (white rounded rect)
    $pad = [single]($Size * $(if ($Maskable) { 0.26 } else { 0.20 }))
    $bodyW = $Size - 2*$pad
    $bodyH = $bodyW * 1.18
    $bodyX = $pad
    $bodyY = ($Size - $bodyH) / 2
    $bodyRect = New-Object System.Drawing.RectangleF($bodyX, $bodyY, $bodyW, $bodyH)
    $br = [single]($Size * 0.06)
    $bd = $br * 2
    $bodyPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $bodyPath.AddArc($bodyX, $bodyY, $bd, $bd, 180, 90)
    $bodyPath.AddArc($bodyX+$bodyW-$bd, $bodyY, $bd, $bd, 270, 90)
    $bodyPath.AddArc($bodyX+$bodyW-$bd, $bodyY+$bodyH-$bd, $bd, $bd, 0, 90)
    $bodyPath.AddArc($bodyX, $bodyY+$bodyH-$bd, $bd, $bd, 90, 90)
    $bodyPath.CloseFigure()
    $white = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $g.FillPath($white, $bodyPath)

    # Display screen (dark) with ¥ symbol
    $scrX = $bodyX + $bodyW*0.10
    $scrY = $bodyY + $bodyH*0.10
    $scrW = $bodyW*0.80
    $scrH = $bodyH*0.34
    $scrRect = New-Object System.Drawing.RectangleF($scrX, $scrY, $scrW, $scrH)
    $scrBr = [single]($Size*0.03); $scrBd = $scrBr*2
    $scrPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $scrPath.AddArc($scrX, $scrY, $scrBd, $scrBd, 180, 90)
    $scrPath.AddArc($scrX+$scrW-$scrBd, $scrY, $scrBd, $scrBd, 270, 90)
    $scrPath.AddArc($scrX+$scrW-$scrBd, $scrY+$scrH-$scrBd, $scrBd, $scrBd, 0, 90)
    $scrPath.AddArc($scrX, $scrY+$scrH-$scrBd, $scrBd, $scrBd, 90, 90)
    $scrPath.CloseFigure()
    $dark = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 28, 42, 56))
    $g.FillPath($dark, $scrPath)

    $fontPx = [int]($scrH * 0.82)
    $font = New-Object System.Drawing.Font("Segoe UI", $fontPx, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $green = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 120, 220, 170))
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $textRect = New-Object System.Drawing.RectangleF($scrX, $scrY, $scrW, $scrH)
    $g.DrawString([char]0x00A5, $font, $green, $textRect, $sf)  # ¥

    # Buttons grid (3 cols x 3 rows) in body lower area
    $btnTop = $scrY + $scrH + $bodyH*0.06
    $btnAreaH = $bodyY + $bodyH - $btnTop - $bodyH*0.08
    $cols = 3; $rows = 3
    $gapX = $bodyW*0.05; $gapY = $bodyH*0.045
    $cw = ($bodyW*0.80 - ($cols-1)*$gapX) / $cols
    $ch = ($btnAreaH - ($rows-1)*$gapY) / $rows
    $btnBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 225, 232, 238))
    $accent = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 34, 160, 110))
    $startX = $bodyX + $bodyW*0.10
    for ($i=0; $i -lt $cols; $i++) {
        for ($j=0; $j -lt $rows; $j++) {
            $bx = $startX + $i*($cw+$gapX)
            $by = $btnTop + $j*($ch+$gapY)
            $bRect = New-Object System.Drawing.RectangleF($bx, $by, $cw, $ch)
            $bR = [single]([Math]::Min($cw,$ch)*0.22); $bD = $bR*2
            $bp = New-Object System.Drawing.Drawing2D.GraphicsPath
            $bp.AddArc($bx, $by, $bD, $bD, 180, 90)
            $bp.AddArc($bx+$cw-$bD, $by, $bD, $bD, 270, 90)
            $bp.AddArc($bx+$cw-$bD, $by+$ch-$bD, $bD, $bD, 0, 90)
            $bp.AddArc($bx, $by+$ch-$bD, $bD, $bD, 90, 90)
            $bp.CloseFigure()
            if ($i -eq 2 -and $j -eq 2) { $g.FillPath($accent, $bp) } else { $g.FillPath($btnBrush, $bp) }
        }
    }

    $g.Dispose()
    return $bmp
}

function Save-Png { param($Bmp, [int]$Target, [string]$Name)
    $out = New-Object System.Drawing.Bitmap($Target, $Target)
    $og = [System.Drawing.Graphics]::FromImage($out)
    $og.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $og.DrawImage($Bmp, 0, 0, $Target, $Target)
    $og.Dispose()
    $file = Join-Path $outDir $Name
    $out.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $out.Dispose()
    Write-Host "  -> $Name ($Target x $Target)"
}

# Render master at 1024 then downscale
$master = Draw-Icon -Size 1024
Save-Png $master 512 'icon-512.png'
Save-Png $master 192 'icon-192.png'
Save-Png $master 180 'apple-touch-icon.png'
Save-Png $master 32  'favicon-32.png'
Save-Png $master 16  'favicon-16.png'
$master.Dispose()

# Maskable: full-bleed square background, central safe zone
$mask = Draw-Icon -Size 512 -Maskable
$mask.Save((Join-Path $outDir 'maskable-512.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$mask.Dispose()
Write-Host "  -> maskable-512.png (512 x 512)"

Write-Host "Icons generated in: $outDir"
