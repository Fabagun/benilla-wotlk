# Upstream merge tracker

This is the operating procedure for synchronizing newly merged upstream pull requests into the
maintainer's manual review tracker. It tracks candidates; it does not decide whether a change is
correct for World of Warcraft 3.3.5a.

## Surfaces

- Upstream repository: `samwhosung/benilla`
- Tracker: `https://github.com/users/Onixaz/projects/1`
- Persistent state: the `Upstream merge checkpoint:` marker in the Project README

Throughout this procedure, Project README means the README attached to that GitHub Project, not the
repository's `README.md`. When new merges are completely synchronized and verified, advancing its
checkpoint is a required final step, not optional cleanup. Leave it unchanged when there are no new
merges or when synchronization is incomplete.

Do not infer the checkpoint from the cards that remain in the Project. Processed cards may be
removed.

## GitHub CLI access

Do not stop solely because `gh auth status` exits non-zero or reports an invalid active token. Its
diagnostic can disagree with the credentials that an individual GitHub command can actually use.
Treat the required operation as authoritative: first run a read-only command such as
`gh project view 1 --owner Onixaz --format json`, then proceed when the Project and upstream API
reads succeed. If an actual required command fails for authentication or authorization, stop before
making changes and report that failure. Do not re-authenticate, replace credentials or change their
permissions unless the user explicitly asks.

## Synchronization procedure

1. Read the checkpoint PR URL and recorded `mergedAt` value from the Project README.
2. Resolve the checkpoint PR from GitHub and confirm its actual `mergedAt` value.
3. Find every upstream PR merged strictly after that timestamp. Compare merge timestamps, not PR
   numbers: an older-numbered PR may merge later.
4. Read the current Project items and compare exact upstream PR URLs.
5. Add every missing upstream PR directly to the Project.
6. Initialize each added PR with:
   - `Status: Todo`
   - `Assessment: Pending review`
   - `Validation: Not checked`
7. GitHub may give an already-merged PR `Status: Done`; override it to `Todo` so it remains visible
   for manual review.
8. Verify that the full eligible set is present and that every newly added card has the required
   values.
9. Only after complete verification, replace the Project README checkpoint with the newest upstream
   PR examined and its `mergedAt` value. Never advance the checkpoint after a partial failure.

If there are no later merged PRs, leave the checkpoint unchanged.

## Scope boundary

Unless the user explicitly requests more work, synchronization must not:

- create issues in `Onixaz/benilla-wotlk`;
- assess whether an upstream change applies to 3.3.5a;
- modify implementation files;
- remove or archive Project items; or
- change fields on previously tracked items.

## Report

Report:

- the previous checkpoint;
- the exact upstream PRs added;
- the new checkpoint;
- whether any eligible PR was already present; and
- whether no new merges were found.
