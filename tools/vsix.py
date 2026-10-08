#!/usr/bin/env python3
"""Package the VS Code extension (editors/vscode) as a .vsix, without vsce or npm.
usage: tools/vsix.py [output.vsix]        (default: build/jot-<version>.vsix)
then:  code --install-extension build/jot-<version>.vsix"""
import json, os, sys, zipfile
from xml.sax.saxutils import escape

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(root, "editors", "vscode")
pkg = json.load(open(os.path.join(src, "package.json")))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "build", f"jot-{pkg['version']}.vsix")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

files = []
for dirpath, _, names in os.walk(src):
    for n in sorted(names):
        if n.endswith(".vsix"): continue
        full = os.path.join(dirpath, n)
        files.append((full, "extension/" + os.path.relpath(full, src)))

manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{pkg['name']}" Version="{pkg['version']}" Publisher="{pkg['publisher']}" />
    <DisplayName>{escape(pkg['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(pkg['description'])}</Description>
    <Tags>jot</Tags>
    <Categories>Programming Languages</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{pkg['engines']['vscode']}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value="" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value="" />
      <Property Id="Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown" Value="true" />
    </Properties>
    <Icon>extension/images/icon.png</Icon>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Icons.Default" Path="extension/images/icon.png" Addressable="true" />
  </Assets>
</PackageManifest>
"""
types = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension=".json" ContentType="application/json"/><Default Extension=".js" ContentType="application/javascript"/><Default Extension=".md" ContentType="text/markdown"/><Default Extension=".png" ContentType="image/png"/><Default Extension=".vsixmanifest" ContentType="text/xml"/></Types>
"""
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("extension.vsixmanifest", manifest)
    z.writestr("[Content_Types].xml", types)
    for full, arc in files:
        z.write(full, arc)
print(out)
