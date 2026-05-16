#Requires -RunAsAdministrator
# Repairs the bnccad:// protocol registration so the web launcher can open BNC CAD.
# Run as Administrator if the button shows "BNC CAD not detected".

$regKey = "HKLM:\Software\BNC CAD"
$installLocation = (Get-ItemProperty -Path $regKey -Name "InstallLocation" -ErrorAction SilentlyContinue).InstallLocation

if (-not $installLocation) {
    # Fall back: search common install locations
    $candidates = @(
        "$env:ProgramFiles\BNC_CAD",
        "C:\BNC_CAD", "D:\BNC_CAD", "E:\BNC_CAD",
        "C:\Program Files\BNC_CAD", "D:\Program Files\BNC_CAD"
    )
    foreach ($path in $candidates) {
        if (Test-Path "$path\bin\FreeCAD.exe") {
            $installLocation = $path
            break
        }
    }
}

if (-not $installLocation -or -not (Test-Path "$installLocation\bin\FreeCAD.exe")) {
    Write-Error "BNC CAD installation not found. Please reinstall BNC CAD."
    exit 1
}

$exe = "$installLocation\bin\FreeCAD.exe"
Write-Host "Registering bnccad:// -> $exe"

New-Item -Path "HKCR:\bnccad" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\bnccad" -Name "(Default)" -Value "URL:BNC CAD"
New-ItemProperty -Path "HKCR:\bnccad" -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Path "HKCR:\bnccad\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\bnccad\DefaultIcon" -Name "(Default)" -Value "`"$exe`",0"
New-Item -Path "HKCR:\bnccad\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\bnccad\shell\open\command" -Name "(Default)" -Value "`"$exe`" `"%1`""

Write-Host "Done. Refresh the browser and try the Open CAD button again."
