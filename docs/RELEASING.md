# Releasing

1. Bump `SLOPPY_VERSION` in `compiler/main.jo` (and `version` in `editors/vscode/package.json`
   when the extension changed: the stores skip a version they already have), add the version's
   section to `CHANGELOG.md` (it becomes the release notes), commit, push.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`.

`.github/workflows/release.yml` then builds and tests everything, makes the GitHub release
(Linux tarball, Windows zip, checksums, the editor extension's .vsix), and publishes the
extension to the VS Code Marketplace and Open VSX.

Publishing the extension needs no stored tokens: the workflow's GitHub OIDC token is exchanged
for short-lived ones. Each store is skipped until it is set up as below. The publishing job runs
in the GitHub environment `marketplace-publish` (Settings → Environments: it can be limited to
`v*` tags there, so nothing else can publish).

To publish an existing release's extension again (after setting a store up, say): Actions →
Release → Run workflow, with the tag.

## VS Code Marketplace (an Azure managed identity)

Once (an Azure account is needed; the free tier is enough, nothing here costs anything):

1. Azure portal → **Managed Identities** → **Create**: any subscription, resource group and
   region; name it e.g. `sloppy-marketplace`.
2. On the new identity: **Settings → Federated credentials → Add credential**:
   scenario **GitHub Actions deploying Azure resources**, organization `david-andrew`,
   repository `sloppy-lang`, entity **Environment**, environment `marketplace-publish`, any name.
3. On the identity: **Settings → Properties**: copy the Client ID and Tenant ID into the
   repository's variables (Settings → Secrets and variables → Actions → Variables):
   `AZURE_CLIENT_ID` and `AZURE_TENANT_ID`. (They are not secrets.)
4. Actions → Release → Run workflow with **only print the Azure identity's Marketplace id**
   checked. In the log of "The identity's Marketplace id", copy the `id` value.
5. https://marketplace.visualstudio.com/manage → the RedFoxLabs publisher → **Members** → **Add**:
   paste that id, role **Contributor**.

From then on, releases publish to the Marketplace. (Personal access tokens stop working for
the Marketplace on 1 December 2026; this does not use one.)

## Open VSX (trusted publishing)

Needs ownership of the RedFoxLabs namespace (being a contributor is not enough), a signed
publisher agreement, and the extension already there with at least one version.

1. https://open-vsx.org → Settings → **Trusted Publishers** → namespace RedFoxLabs →
   **GitHub Actions**: owner `david-andrew`, repository `sloppy-lang`, workflow `release.yml`,
   environment `marketplace-publish`.
2. Repository variable `OPENVSX_TRUSTED` = `true`.

From then on, releases publish to Open VSX.
