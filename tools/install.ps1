# Install Sloppy on Windows, in PowerShell:
#   irm https://sloppy-lang.org/install.ps1 | iex
#   $env:SLOPPY_WANT = "v0.3.0"; irm https://sloppy-lang.org/install.ps1 | iex     (a version)
# Installs to %LOCALAPPDATA%\sloppy (or $env:SLOPPY_INSTALL): bin\sloppy.exe and the standard
# library beside it, and puts its bin on your PATH. Running it again updates.
# (`sloppy update` runs it with SLOPPY_CURRENT, the version installed: nothing to do if it is the
# latest. Settings come in environment variables: a script run by iex takes no arguments.)
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'      # (the progress bar makes downloads slow)
    $Repo = 'david-andrew/sloppy-lang'
    $Asset = 'sloppy-windows-x86_64.zip'
    $Version = if ($env:SLOPPY_WANT) { $env:SLOPPY_WANT } else { 'latest' }
    $Install = if ($env:SLOPPY_INSTALL) { $env:SLOPPY_INSTALL } else { Join-Path $env:LOCALAPPDATA 'sloppy' }
    $Given = [bool]$env:SLOPPY_WANT
    $Current = $env:SLOPPY_CURRENT
    # (they would stay set in this PowerShell for the next run)
    Remove-Item Env:SLOPPY_WANT, Env:SLOPPY_CURRENT -ErrorAction SilentlyContinue

    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "Sloppy's compiler makes x86-64 programs and runs on 64-bit Windows"
    }
    # (Windows PowerShell 5.1 may not offer TLS 1.2 by itself)
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    if ($Version -eq 'latest') {
        # which version that is: where releases/latest leads (.../releases/tag/vX.Y.Z)
        try {
            $req = [Net.WebRequest]::Create("https://github.com/$Repo/releases/latest")
            $req.AllowAutoRedirect = $false
            $resp = $req.GetResponse()
            $tag = ($resp.Headers['Location'] -split '/')[-1]
            $resp.Close()
            if ($tag -match '^v[0-9]') { $Version = $tag }
        } catch { }
    }
    if ($Version -eq 'latest') {
        $base = "https://github.com/$Repo/releases/latest/download"
    } else {
        if (-not $Version.StartsWith('v')) { $Version = "v$Version" }
        $base = "https://github.com/$Repo/releases/download/$Version"
        if ($Current -and $Version -eq "v$Current") {
            if ($Given) { Write-Host "sloppy $Current is the version installed: nothing to do" }
            else { Write-Host "sloppy $Current is the latest version: nothing to update" }
            return
        }
    }
    # (SLOPPY_DOWNLOAD_BASE: somewhere else holding the release files, for testing)
    if ($env:SLOPPY_DOWNLOAD_BASE) { $base = $env:SLOPPY_DOWNLOAD_BASE }

    # ---- download and check ----
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("sloppy-install-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $zip = Join-Path $tmp $Asset
        Write-Host "downloading $base/$Asset" -ForegroundColor DarkGray
        try { Invoke-WebRequest -UseBasicParsing -Uri "$base/$Asset" -OutFile $zip }
        catch { throw "could not download $base/$Asset (is there a release $Version?)" }
        $sum = $null
        try { $sum = (Invoke-RestMethod -UseBasicParsing -Uri "$base/$Asset.sha256") } catch { }
        if ($sum) {
            $want = (([string]$sum).Trim() -split '\s+')[0].ToLower()
            $have = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
            if ($want -ne $have) { throw "the download is damaged (checksum $have, expected $want)" }
        }
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        $src = Get-ChildItem -Path $tmp -Directory -Filter 'sloppy-*' | Select-Object -First 1
        if (-not $src -or -not (Test-Path (Join-Path $src.FullName 'bin\sloppy.exe'))) { throw "the download does not hold bin\sloppy.exe" }

        # ---- install (replacing an earlier one whole: no stale library files) ----
        # (a running sloppy.exe, as under `sloppy update`, cannot be deleted, but it can be renamed)
        $bin = Join-Path $Install 'bin'
        $old = Join-Path $bin 'sloppy.old.exe'
        if (Test-Path $Install) {
            Remove-Item $old -Force -ErrorAction SilentlyContinue
            $exe = Join-Path $bin 'sloppy.exe'
            if (Test-Path $exe) { Move-Item $exe $old -Force }
            Get-ChildItem -Path $Install -Force | Where-Object { $_.Name -ne 'bin' } | Remove-Item -Recurse -Force
            if (Test-Path $bin) { Get-ChildItem -Path $bin -Force | Where-Object { $_.Name -ne 'sloppy.old.exe' } | Remove-Item -Recurse -Force }
        }
        New-Item -ItemType Directory -Path $Install -Force | Out-Null
        Copy-Item -Path (Join-Path $src.FullName '*') -Destination $Install -Recurse -Force
        Remove-Item $old -Force -ErrorAction SilentlyContinue
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    $installed = & (Join-Path $bin 'sloppy.exe') --version
    if ($LASTEXITCODE -ne 0 -or -not $installed) { throw "$bin\sloppy.exe does not run on this machine" }

    # ---- on the PATH (the user's, for new terminals, and this one's) ----
    $note = ''
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @()
    if ($userPath) { $parts = $userPath -split ';' | Where-Object { $_ } }
    if ($parts -notcontains $bin) {
        [Environment]::SetEnvironmentVariable('Path', (($parts + $bin) -join ';'), 'User')
        $note = "added $bin to your PATH"
    }
    if (($env:Path -split ';') -notcontains $bin) { $env:Path = "$bin;$env:Path" }

    # ---- done ----
    Write-Host ''
    if ($Current) {
        Write-Host "sloppy $Current was replaced by $installed in $Install" -ForegroundColor Green
        if ($note) { Write-Host $note -ForegroundColor DarkGray }
        return
    }
    Write-Host "$installed was installed to $Install" -ForegroundColor Green
    if ($note) { Write-Host "$note (terminals opened from now on have it; this one does too)" -ForegroundColor DarkGray }
    Write-Host ''
    Write-Host 'Then:'
    Write-Host '  sloppy game.jo         compile and run a program' -ForegroundColor Cyan
    Write-Host '  sloppy --web game.jo   the same in the browser' -ForegroundColor Cyan
    Write-Host '  sloppy build game.jo   game.exe' -ForegroundColor Cyan
    $editor = $null
    if (Get-Command cursor -ErrorAction SilentlyContinue) { $editor = 'cursor' }
    elseif (Get-Command code -ErrorAction SilentlyContinue) { $editor = 'code' }
    if ($editor) {
        Write-Host ''
        Write-Host 'Editor support (highlighting, errors as you type, completion...):'
        Write-Host "  $editor --install-extension RedFoxLabs.sloppy" -ForegroundColor Cyan
    }
    Write-Host ''
    Write-Host "Docs: https://sloppy-lang.org  -  update: sloppy update  -  uninstall: delete $Install" -ForegroundColor DarkGray
}
