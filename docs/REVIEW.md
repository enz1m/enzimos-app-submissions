# Reviewer operations

Only repository reviewers manage review labels and approve release promotion.
Initial reviewer registry: `reviewers.json`. Labels are human-maintained review
states, not an automatic claim that a build or verification happened.

## Initial review

- Associate the issue, manifest PR and proposed source revision.
- Confirm upstream/app-ID ownership and redistribution rights. Record the method
  and result, without publishing private evidence. Check nominated maintainers.
- Review listing text, privacy/data statement, support route, icon and genuine
  screenshots. Review AppStream identity, licence, release and screenshot data.
- Inspect pinned source/dependency changes and all sandbox permissions. Passing
  structure checks does not prove absence of hidden network downloads or malware.
- Apply `approved-for-build` only to the exact reviewed PR HEAD. If new commits
  arrive, re-review the changes; GitHub dismisses stale PR approvals.
- Build the approved manifest in a disposable Flatpak SDK environment without
  production keys, repository tokens, privileged mounts or persistent workers.
  Use normal `flatpak-builder --repo=UNSIGNED_REPO ... manifest.json` on that
  isolated worker. Do not run app commands in the metadata workflow.
- Install and launch the app from its unsigned candidate in a disposable test
  installation. Check exported metadata, runtime/dependency resolution, portal
  behaviour and representative core operation. Use a test-only key where needed.
- Record source, manifest and output commit, runtime/test results and decision
  in the review. Merge only after required checks and review. Merging records
  reviewed packaging; it is NOT release publication.
- Update the private curated catalog and server app-ID allowlist, import ONLY
  that approved ref to the trusted release repository, sign, and deploy using
  the private infrastructure pipeline. Its signing/upload keys never enter here.
- After public client verification, apply `published` and link the published
  listing/release. A failed build returns to `changes-requested` with diagnostics.

## Update review

The trusted validator checks the PR actor against BASE metadata maintainers;
adding oneself to the proposed maintainer list grants no update authority.
Review source pin/version/changelog and permission diff, and recheck screenshots
if UI changed. Source-host changes, privacy changes, maintainers or app identity
require ownership/permission review again. A former maintainer cannot transfer
an app merely by editing a username; confirm transfer out of band and record it.

## Decline, withdrawal and incidents

Explain declines and offer a path to correct objective issues. Keep duplicate
submissions linked to the original. Freeze disputed IDs and takeovers; do not
hand them to the first new claimant. For serious security/licensing issues,
freeze publication, investigate privately and publish a reviewed fix/rollback
or EOL notice. Delisting is not remote removal from installed users' computers.

A rollback is a new approved signed release of the reviewed older app; replaying
an old signed transport archive is refused by the delivery server. Revoking a
maintainer means updating the trusted registry and reviewer decision, not merely
closing an issue. Collect only necessary public metadata; do not request IDs,
payment details, private tokens or secrets in public issues.

## Checks and protections

Required status: `Review submission metadata`. The PR-target workflow has only
read access, checks out the trusted BASE policy separately, parses proposed
files as data and contains no app build step or deployment credentials. Tests
run from the base policy too. A separate push check validates merged metadata.
The new boundary test covers legitimate intake and refused unauthorised updates
and assets; there is no existing test of this new public admission boundary to
extend. No fixture app is advertised as a real submission or installed app.

Keep one code-owner approval, stale-approval dismissal, required metadata status,
resolved conversations and no force pushes/deletions on main. With only one
reviewer, that reviewer cannot approve their own PR; add an independent trusted
reviewer before using the PR route for reviewer-authored policy changes.
