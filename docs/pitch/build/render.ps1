param([string]$In,[string]$Out)
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open($In, $true, $false, $false)
$pres.SaveAs($Out, 32)
$pres.Close()
$app.Quit()
