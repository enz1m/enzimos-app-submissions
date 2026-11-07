# Submission requirements

## Listing and developer

Use a stable reverse-DNS application ID. Provide the public source repository,
an exact 40-character Git commit, version, release notes, licence identifier,
homepage, support URL, privacy-policy URL and an accurate data-collection
statement. Include a short summary, full description, categories and the GitHub
usernames and stable numeric GitHub IDs authorised to maintain the app. The dashboard records these automatically; raw manifest contributors include the `maintainer_ids` map. The submitter must be among those
maintainers; recording a username is not ownership verification.

Demonstrate control of the upstream project or relevant domain using a link
from the authoritative project, a reviewer-requested public domain token, or
another reviewer-approved proof. Never publish credentials, private contact
records or personal identity documents. A GitHub username alone does not prove
control of a reverse-DNS namespace. Publisher verification and app safety are
separate review questions.

We initially accept apps with public source and a licence that permits binary
redistribution. No proprietary binary-upload route is available. Explain any
third-party assets or dependency licence obligations. Do not submit someone
else's app under a new identity without permission or a clearly identified,
permitted independent fork.

## Screenshots and icon

Provide at least one real, current screenshot; two or more are recommended.
Screenshots must show the app rather than a marketing mockup, use no private
user data, and be images you may redistribute. Add a useful caption for each.

- One to eight PNG, JPEG or WebP screenshots, each at most 8 MiB.
- At least 640 × 360 and at most 3840 × 2160 pixels for the initial desktop
  programme. These are enzim Apps intake limits, not claimed Flatpak limits.
- PNG icon, square, 128–1024 pixels (512 recommended), at most 2 MiB.
- Keep screenshots under `apps/APP_ID/screenshots/`; use `icon.png` for the icon.
  Do not submit SVG/HTML or externally mutable images as the published assets.
- Include matching AppStream metadata in `metainfo.xml` and screenshot captions.
  The reviewer checks AppStream consistency and actual UI quality; the automated
  validator checks the image files and core AppStream identity.

GitHub's issue form accepts initial screenshot/icon uploads. The canonical
reviewed assets must also be committed in the app PR; attachment links alone
are not the release asset inventory.

## Build and permissions

Supply a JSON Flatpak manifest with `app-id`, `runtime`, `runtime-version`,
`sdk`, `command`, `finish-args` and `modules`. Use public HTTPS sources. Pin
all Git modules to full commits and archives/files to SHA-256. No moving tags,
branches, local directory sources or inline downloaded binaries. JSON is the
initial manifest format; YAML can be converted to JSON before submission.

Declare public source locations for dependencies. Fetches during build must be
represented as pinned sources rather than `curl | sh` or hidden Cargo/npm
network calls. CI catches structurally unpinned sources; a reviewer must inspect
build commands for hidden downloads and other behaviour.

Explain every requested Flatpak permission, including filesystem, bus, network,
device and socket access. Prefer portals and narrow permissions. Broad home,
host filesystem, system/session bus, unrestricted devices or privilege requests
require explicit justification and may be declined. Build/run/install tests must
pass on the target runtime before publication; metadata CI alone is insufficient.

Keep each app PR limited to that app's directory and assets. Proposals to change
review policy or tools go through an issue and a reviewer-authored change.

## Dashboard build manifests

The developer-side builder accepts self-contained JSON manifests. When the
manifest is stored in the same GitHub repository as the app, set the main Git
source commit to `@ENZIM_SOURCE_COMMIT@` and `disable-submodules` to true. The
builder resolves that placeholder to the selected release commit. All other
Git dependencies need full commits, and downloads need SHA-256. Canonical
submission exports resolve the placeholder before this repository validates
them. No app build runs inside the trusted PR metadata workflow.

See https://flatpak.enzim.dev/agents.md for CLI/API onboarding and optional
app configuration. All publication decisions remain manual.
