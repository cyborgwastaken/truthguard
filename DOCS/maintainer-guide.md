# Maintainer Guide (for the project lead)

This is your playbook for running the repo: reviewing and merging pull requests (PRs), keeping the board accurate, and handling problems. It is written for cyborgwastaken.

## 1. How the repo is protected

| Setting | Value | What it means |
|---|---|---|
| Branch `main` | protected | Changes must come through a pull request |
| Required approvals | 1, **from a code owner** | `.github/CODEOWNERS` makes you the owner of everything, so only your approval counts. A teammate approving another teammate's PR does not unlock the merge |
| Stale approvals | dismissed on new commits | If someone pushes after you approved, approve again |
| Conversations | must be resolved | Open review comments block the merge |
| Force pushes, branch deletion | blocked | History of `main` cannot be rewritten |
| Merge method | **squash only** | Each PR becomes one commit on `main`, titled with the PR title (`T03: ...`) |
| Merged branches | deleted automatically | No branch clutter |
| Admin enforcement | **off** | You (an admin) can bypass the rules. Teammates cannot |

Because admin enforcement is off, **GitHub will let you push straight to `main`**. Do not. Use a PR for your own work as well. The bypass exists for one reason: you cannot approve your own PR, so for your own tickets you merge with the admin override (section 4).

To view the settings: GitHub -> repo -> Settings -> Branches, or `gh api repos/cyborgwastaken/truthguard/branches/main/protection`.

## 2. Should we have a `dev` branch? Recommendation: no

Your idea: all ticket branches merge into `dev`; only you merge `dev` into `main`. It sounds safe, but for this team I would not do it.

**What `dev` would give us:** a place where unfinished work can pile up while `main` stays "clean".

**What it costs:**
- Every ticket merges twice (branch -> dev, dev -> main), and conflicts can appear twice.
- You review each PR into `dev` anyway, so the `dev` -> `main` PR adds no new information. It is a large batch of already-reviewed changes that is hard to review again.
- The danger moves to the end: the big merge to `main` happens near the demo, when there is no time to fix surprises.
- `dev` drifts from `main` and people branch from the wrong one. With five people new to Git, this is the most likely source of confusion.
- Wave 3 and 4 tickets depend on earlier ones being merged. Delaying merges into `main` delays everyone.

**What we do instead (already set up):**
1. `main` is protected and every change is reviewed by you. That is the same gate `dev` would provide, with one hop instead of two.
2. Each PR must pass its tests locally before you merge (section 3). When we add CI (see below), it will be a required check.
3. When we have a version that works end to end, tag it: `git tag demo-1 && git push origin demo-1`. Tags are your "known good" markers, and the demo can run from one.

**When a `dev` branch becomes worth it:** if people outside the team start using `main` (a live deployment, other teams depending on it), or if you want an unreviewed integration area. Neither applies now. If you still want it, say so and I will set it up: create `dev`, protect it the same way, make it the default branch, and update the team docs (about 30 minutes).

**Recommended next step:** add a GitHub Actions workflow that runs both test suites on every PR and mark it as a required check. Then "tests pass" is enforced by GitHub, not by trust. Ask for it when you want it.

## 3. Reviewing a pull request, step by step

You get an email or notification when a PR is opened. Teammates are told to add you as reviewer.

**Step 1: Understand what it should do.** Open the linked issue (the PR says `Closes #N`). Read "Done when". That is your acceptance checklist.

**Step 2: Read the PR page.** Check the title (`T03: <ticket title>`), the description, and the **Files changed** tab. Look at the size. A PR touching unrelated files, or hundreds of lines for a small ticket, should be split.

**Step 3: Run it yourself.** In your terminal:
```bash
gh pr checkout 33                       # replace with the PR number
source .venv/bin/activate
(cd BACKEND && pip install -r requirements.txt && alembic upgrade head)
(cd AGENT && python -m pytest) && (cd BACKEND && python -m pytest)
```
Run anything else the PR says to check (the "How to check it" section). When you are done: `git checkout main`.

**Step 4: Review checklist**
- [ ] Every "Done when" item is met. Can you point to the file or test that proves it?
- [ ] Tests exist for new logic, and they pass.
- [ ] Shared models in `AGENT/truthguard_agent/schemas/` are used, not re-invented. Changing them needs a note on the issue first because other roles depend on them.
- [ ] Nothing is invented: missing metadata stays `None`/`null`/"unknown".
- [ ] Failures are visible (explicit status, no silent success).
- [ ] Retrieved document text is treated as untrusted data.
- [ ] No secrets, `.env`, `.venv`, `node_modules`, or unrelated files.
- [ ] Python 3.9 compatible (`Optional[X]`, no `X | None` at runtime).
- [ ] The change stays inside the ticket.
- [ ] No overclaiming (no trust score, no "better than baseline" without measurements).
- [ ] Commit messages start with the ticket id and have no AI co-author line.

**Step 5: Leave your review.** On the PR: **Files changed -> Review changes**. Comment on specific lines. Be specific and kind: say what to change and why, and mark each as "must fix" or "optional". Then choose:
- **Approve**: ready to merge.
- **Request changes**: must be fixed first.
- **Comment**: questions only.

From the terminal: `gh pr review 33 --approve -b "Looks good, tests pass."` or `gh pr review 33 --request-changes -b "See comments."`

**Step 6: Re-review.** The author fixes and pushes to the same branch; the PR updates itself and your old approval is dismissed. Look at the new commits only, then approve again. Ask the author to click "Resolve conversation" on comments they have addressed (or resolve them yourself once you have checked).

## 4. Merging

When the checklist passes:

1. **Approve** the PR (not for your own PRs, see below).
2. Make sure the PR title is `T<nn>: <ticket title>`. Squash merge uses it as the commit message.
3. Click **Squash and merge** (the only option), or:
   ```bash
   gh pr merge 33 --squash
   ```
4. The branch is deleted automatically and the issue closes because of `Closes #N`.
5. **Update the board:** make sure the card is in **Done**. Check whether the board did it by itself the first time you merge. If not, run:
   ```bash
   OPS/github/move_card.sh 4 done      # issue number, then: backlog | ready | in-progress | in-review | done
   ```
6. **Unblock the next tickets.** Open `DOCS/backlog.md` and find tickets whose "Depends on" are now all Done. Move them to Ready:
   ```bash
   OPS/github/move_card.sh 7 ready
   ```
   Then tell the owner (comment on the issue or message them). Example: when T02 and T03 are both Done, T06 and T07 become Ready.
7. **Tell the author** it is merged and what to do next: `git checkout main && git pull`, then start the next ticket.
8. Pull on your machine too: `git checkout main && git pull`.

### Your own PRs

You cannot approve your own PR. Open the PR as usual, run the checks on it, and when satisfied use the admin override: on the PR page click **Merge without waiting for requirements to be met (administrators only)**, or `gh pr merge 33 --squash --admin`. If you would rather have a second pair of eyes on important changes, ask a teammate to read it and comment first. Their approval will not satisfy the rule but their comments are useful.

## 5. When things go wrong

| Situation | What to do |
|---|---|
| Tests fail on the PR | Request changes; paste the failing command and output in the comment |
| Merge conflict ("This branch has conflicts") | The author runs `git checkout main && git pull && git checkout <branch> && git merge main`, fixes the conflict markers, commits, pushes. Walk them through it the first time |
| PR is huge or mixes tickets | Ask the author to split it. One ticket = one PR |
| Author pushed after your approval | The approval was dismissed on purpose. Review the new commits and approve again |
| Wrong things merged | Use GitHub's **Revert** button on the merged PR. It opens a new PR that undoes it; review and merge that. Do not force-push `main` |
| A secret (API key) was committed | Assume it is leaked. **Rotate the key first**, then remove it from the code with a new PR. Rewriting history is a second step and not a substitute for rotating |
| Someone is stuck for a long time | Look at their issue/PR, ask what they tried, and consider pairing with their secondary developer |
| Two people need to change the same file | Ask them to coordinate on the issue; the one finishing first merges, the other merges `main` into their branch |
| A ticket's interface needs to change after others started | Discuss on the issue, update the issue text and the role doc in `DOCS/team/`, and tell everyone affected |

## 6. Keeping the board accurate

The board is the team's shared memory. Each week, or at each wave change:

- Every ticket being worked on is **In progress**, every open PR is **In review**, every merged ticket is **Done**.
- When all tickets of a wave are Done, move the next wave's tickets that are unblocked to **Ready**.
- Bring up tickets that have sat in **In progress** for more than two days without a commit or comment.
- Assign people once they accept their invites: `python3 OPS/github/create_backlog.py --assign`.
- If ownership changes, edit the `ROLES` table in `OPS/github/create_backlog.py`, run `--reassign`, and update `DOCS/team/` and `DOCS/instructions.md`.

## 7. Milestones and releases

- Tag known-good versions: `git tag demo-1 && git push origin demo-1`.
- Before the demo: freeze merging (only fixes), run the full setup from [setup.md](setup.md) on a clean clone, run the demo script three times, and tag the result.

## 8. Quick command reference

```bash
gh pr list                              # open PRs
gh pr view 33 --web                     # open a PR in the browser
gh pr checkout 33                       # get a PR's code locally
gh pr diff 33                           # see the changes in the terminal
gh pr review 33 --approve               # or --request-changes -b "why"
gh pr merge 33 --squash                 # merge (add --admin for your own PRs)
OPS/github/move_card.sh 4 done          # move a card on the board
gh issue list --state open              # remaining tickets
git checkout main && git pull           # always before starting something new
```
