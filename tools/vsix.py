#!/usr/bin/env python3
"""Package the VS Code extension (editors/vscode) as a .vsix, without vsce or npm.
usage: tools/vsix.py [output.vsix]        (default: build/sloppy-<version>.vsix)
then:  code --install-extension build/sloppy-<version>.vsix"""
import json, os, sys, zipfile
from xml.sax.saxutils import escape

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(root, "editors", "vscode")
pkg = json.load(open(os.path.join(src, "package.json")))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "build", f"sloppy-{pkg['version']}.vsix")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

repo = pkg['repository']['url']
# (as vsce does: the keywords, the languages and their file extensions)
langs = pkg['contributes']['languages']
tags = ','.join(dict.fromkeys(pkg.get('keywords', []) + [l['id'] for l in langs] + ['__ext_' + e.lstrip('.') for l in langs for e in l.get('extensions', [])]))

files = []
for dirpath, _, names in os.walk(src):
    for n in sorted(names):
        if n.endswith(".vsix"): continue
        full = os.path.join(dirpath, n)
        arc = "extension/" + os.path.relpath(full, src)
        # (as vsce does: the marketplace fails, "TF400898: An Internal Error Occurred", on a file
        # without an extension, whose content type would be the one for "")
        if arc == "extension/LICENSE": arc += ".txt"
        if arc == "extension/README.md": arc = "extension/readme.md"
        files.append((full, arc))

manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{pkg['name']}" Version="{pkg['version']}" Publisher="{pkg['publisher']}" />
    <DisplayName>{escape(pkg['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(pkg['description'])}</Description>
    <Tags>{escape(tags)}</Tags>
    <Categories>Programming Languages</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{pkg['engines']['vscode']}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.EnabledApiProposals" Value="" />
      <Property Id="Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown" Value="true" />
      <Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true" />
      <Property Id="Microsoft.VisualStudio.Services.Content.Pricing" Value="Free" />
      <Property Id="Microsoft.VisualStudio.Services.Links.Source" Value="{repo}" />
      <Property Id="Microsoft.VisualStudio.Services.Links.Getstarted" Value="{pkg['homepage']}" />
      <Property Id="Microsoft.VisualStudio.Services.Links.GitHub" Value="{repo}" />
      <Property Id="Microsoft.VisualStudio.Services.Links.Support" Value="{pkg['bugs']['url']}" />
      <Property Id="Microsoft.VisualStudio.Services.Links.Learn" Value="{pkg['homepage']}" />
    </Properties>
    <License>extension/LICENSE.txt</License>
    <Icon>extension/images/icon.png</Icon>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/readme.md" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Icons.Default" Path="extension/images/icon.png" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE.txt" Addressable="true" />
  </Assets>
</PackageManifest>
"""
# a content type for each extension in the package
mime = {".js": "application/javascript", ".json": "application/json", ".md": "text/markdown",
        ".png": "image/png", ".txt": "text/plain", ".vsixmanifest": "text/xml"}
exts = sorted({os.path.splitext(arc)[1].lower() for _, arc in files} | {".vsixmanifest"})
for e in exts:
    if e not in mime: sys.exit(f"vsix.py: no content type for {e!r} files (add it to mime)")
types = ('<?xml version="1.0" encoding="utf-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         + "".join(f'<Default Extension="{e}" ContentType="{mime[e]}"/>' for e in exts) + "</Types>\n")
def entry(name):
    i = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    i.external_attr = 0o100644 << 16       # a regular file, rw-r--r--
    i.compress_type = zipfile.ZIP_DEFLATED
    return i
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(entry("extension.vsixmanifest"), manifest)
    z.writestr(entry("[Content_Types].xml"), types)
    for full, arc in files:
        z.writestr(entry(arc), open(full, "rb").read())
print(out)
