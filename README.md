# Submit an app to enzim Apps

This is the **public submission and review repository** for
[enzim Apps](https://flatpak.enzim.dev/developers.html). Anyone with a GitHub
account can submit an app. Publication requires review, an isolated build,
install/run testing and signed release promotion. This repository has no
production signing keys, upload credentials or automatic publication job.

## Submit through the developer dashboard

The normal route is [Sign in with GitHub](https://flatpak.enzim.dev/dashboard.html): connect your public app repository, select a release, and complete the listing/screenshots. The service pins its source commit and keeps updates attached to stable GitHub account/repository IDs. No developer PR is required for this route. Review stages are visible in the dashboard and [public review queue](https://flatpak.enzim.dev/reviews.html). The reviewer handles packaging help, canonical review, isolated testing and private signed promotion.

## Advanced: submit packaging directly

1. Read the [submission requirements](docs/REQUIREMENTS.md).
2. [Open the New app form](https://github.com/enz1m/enzimos-app-submissions/issues/new?template=new-app.yml).
   Supply your app details, pinned public source, manifest, ownership evidence,
   icon and screenshots. GitHub handles sign-in and file uploads. All submitted
   material is PUBLIC: do not upload passwords, keys, private documents or
   sensitive account/ownership evidence.
3. Submit a matching pull request under `apps/YOUR.APP.ID/` using the
   [metadata example](docs/submission.example.json). A reviewer can help you
   prepare it from the issue; the issue alone does not become a package.
4. Respond to review requests in the same issue/PR. Keep screenshots current.
   CI checks metadata, pinned inputs, assets and update ownership. It does NOT
   claim to check whether application code is safe or whether the app launches.
5. A reviewer approves the exact source/manifest, builds it in isolation, tests
   installation and launch, and hands the exact approved artifact to the private
   signing pipeline. The app appears in the store only after publication.

Initial policy: **public-source applications only**, with a licence permitting
redistribution. Open-source submissions do not require a publisher fee under
this initial programme; no paid developer account service has been introduced.
Project apps already distributed before this intake opened remain a separate
release cohort and do not imply their sources have been publicly mirrored.

## Update an approved app

Select your app in the [developer dashboard](https://flatpak.enzim.dev/dashboard.html)
and choose its next release. For direct packaging contributions, use the
[Update app form](https://github.com/enz1m/enzimos-app-submissions/issues/new?template=update-app.yml)
and a PR changing only your app directory. The actor’s numeric GitHub ID must be one of the
maintainers in the existing approved metadata (or a repository reviewer).
Always include the new immutable source revision, version and release notes.
Every update needs review. Permission expansion, maintainer/ownership changes,
source-host changes and material branding/privacy changes need renewed review.
A previously approved app does not get unlimited direct publishing access.

## Track your submission

[Open submissions](https://github.com/enz1m/enzimos-app-submissions/issues) and
[manifest reviews](https://github.com/enz1m/enzimos-app-submissions/pulls) are public.
Reviewers maintain these labels:

| Stage | Meaning |
| --- | --- |
| `submitted` | Request received; no approval implied |
| `in-review` | Reviewer checking ownership, metadata, permissions and source |
| `needs-information` / `changes-requested` | Developer action needed |
| `approved-for-build` | Exact source and manifest approved for an isolated build |
| `testing` | Build/install/runtime checks in progress |
| `published` | Signed release deployed; reviewer links its app/release |
| `declined` / `withdrawn` / `end-of-life` | Closed or retired, with an explanation |

An issue closing or a PR merging does not itself publish software. No fixed
review time is promised. Initial reviewer: [@enz1m](https://github.com/enz1m).
Appeal a decline by commenting on the existing issue with new evidence; app-ID
and ownership disputes remain frozen until the reviewer resolves them.

## Repository boundaries

App contributions contain `submission.json`, `manifest.json`, `metainfo.xml`,
`icon.png` and `screenshots/`. Do not submit executable CI helpers, submodules,
symlinks, vendored SDKs or prebuilt binary uploads. Flatpak manifest build
instructions run only in the separately approved build environment.

The required read-only PR metadata check runs the validator from the BASE
revision and treats the proposed tree as data. It never executes proposed
Python, workflow files, manifests or build commands. `main` requires code-owner
review and the metadata check, dismisses stale approvals and blocks force pushes.
The owner can administer repository rules; rules do not replace private signing.
See [review operations](docs/REVIEW.md) and [security reporting](SECURITY.md).

Scripts and documentation authored here use the MIT licence. Submitted app
code and assets retain their own declared licences; submission does not
relicense third-party work. Include the permissions needed to redistribute it.
