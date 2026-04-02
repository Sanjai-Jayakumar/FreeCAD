# Enable Assembly Workbench for BNC CAD
# Run this script if Assembly workbench is not visible
param([switch]$NonInteractive)

Write-Host "=========================================="
Write-Host "  BNC CAD - Enable Assembly Workbench"
Write-Host "=========================================="
Write-Host ""

$userCfg = "$env:APPDATA\FreeCAD\user.cfg"

# Create FreeCAD config directory if it doesn't exist
$configDir = "$env:APPDATA\FreeCAD"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Write-Host "Created FreeCAD config directory"
}

if (Test-Path $userCfg) {
    Write-Host "Found existing user.cfg"
    Write-Host "Creating backup..."
    Copy-Item $userCfg "$userCfg.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')" -Force
    Write-Host ""
    
    # Read the config
    $content = Get-Content $userCfg -Raw
    
    # Check if Assembly is already enabled
    if ($content -match '<FCBool Name="AssemblyWorkbench" Value="1"/>') {
       Write-Host "Assembly workbench is already enabled!"
    }
    elseif ($content -match '<FCParamGroup Name="Enabled">') {
        Write-Host "Adding Assembly workbench to enabled list..."
        
        # Add Assembly to enabled workbenches
        $newContent = $content -replace '(<FCParamGroup Name="Enabled">)', "`$1`n      <FCBool Name=`"AssemblyWorkbench`" Value=`"1`"/>"
        
        $newContent | Set-Content $userCfg -Encoding UTF8
        Write-Host "✓ Assembly workbench enabled!"
    }
    else {
        Write-Host 'Please enable Assembly manually:'
        Write-Host '1. Open BNC CAD'
        Write-Host '2. Edit -> Preferences...'
        Write-Host '3. Go to Workbenches section'
        Write-Host '4. Move Assembly from Disabled to Enabled list'
        Write-Host '5. Click OK and restart BNC CAD'
    }
}
else {
    Write-Host "user.cfg not found - will be created on first launch"
    Write-Host ""
    Write-Host "Please do this:"
    Write-Host "1. Launch BNC CAD (it will create user.cfg)"
    Write-Host "2. Close BNC CAD"  
    Write-Host "3. Run this script again"
    Write-Host ""
    Write-Host 'OR manually enable Assembly:'
    Write-Host '1. Open BNC CAD'
    Write-Host '2. Edit -> Preferences -> Workbenches'
    Write-Host '3. Move Assembly from Disabled to Enabled'
    Write-Host '4. Restart BNC CAD'
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Please restart BNC CAD to see changes"
Write-Host "=========================================="
Write-Host ""
if ([Environment]::UserInteractive -and -not $NonInteractive) {
    Read-Host "Press Enter to exit"
}
