"""Tests for OPS/github/board_sync.py. Run: python -m pytest OPS/tests"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "github"))

import board_sync as bs  # noqa: E402


def make_board(spec):
    """spec: {number: (tid, deps, status[, state])} with deps given as issue numbers."""
    tickets = []
    for number, values in spec.items():
        tid, deps, status = values[:3]
        state = values[3] if len(values) > 3 else "OPEN"
        tickets.append(bs.Ticket(number, tid, deps, "dev%d" % number, state, status))
    return bs.Board(tickets)


def statuses(board):
    return {t.tid: t.status for t in board.tickets.values()}


def chain():
    # T06 (#7) needs T02+T03; T11 (#12) needs T04+T06; T08 (#9) needs T07
    return make_board({
        3: ("T02", [], "Done", "CLOSED"),
        4: ("T03", [], "Done", "CLOSED"),
        5: ("T04", [], "Done", "CLOSED"),
        7: ("T06", [3, 4], "Ready"),
        8: ("T07", [3, 4], "In progress"),
        9: ("T08", [8], "Backlog"),
        12: ("T11", [5, 7], "Backlog"),
        30: ("T29", [], "Backlog"),
    })


def pr(number=41, body="Closes #7", draft=False, merged=False):
    return {"number": number, "body": body, "draft": draft, "merged": merged}


# ---- parsing -------------------------------------------------------------------------------------

def test_closing_keywords():
    assert bs.closing_issues("Closes #7") == [7]
    assert bs.closing_issues("fixes #7 and resolved: #9, Closed #7") == [7, 9]
    assert bs.closing_issues("CLOSES #12") == [12]


def test_refs_and_plain_mentions_do_not_count():
    assert bs.closing_issues("Refs #6") == []
    assert bs.closing_issues("see #7, related to #9") == []
    assert bs.closing_issues("Disclosed #7") == []
    assert bs.closing_issues(None) == []
    assert bs.closing_issues("") == []


# ---- branch created ------------------------------------------------------------------------------

def test_branch_for_a_ready_ticket_moves_it_to_in_progress():
    board = chain()
    bs.on_branch_created(board, "t06-documents-api", "branch")
    assert statuses(board)["T06"] == "In progress"


def test_branch_for_a_blocked_ticket_also_starts_it():
    board = chain()
    bs.on_branch_created(board, "t11-chat-ui", "branch")
    assert statuses(board)["T11"] == "In progress"


def test_other_branches_and_tags_change_nothing():
    for ref, ref_type in [("chore-board", "branch"), ("t06-x", "tag"), ("main", "branch"), ("t99-x", "branch"),
                          ("tfoo-x", "branch"), ("t06", "branch")]:
        board = chain()
        before = statuses(board)
        bs.on_branch_created(board, ref, ref_type)
        assert statuses(board) == before, ref


def test_branch_for_a_finished_or_reviewed_ticket_does_not_move_it_back():
    board = chain()
    bs.on_branch_created(board, "t02-fixes", "branch")  # T02 is Done
    assert statuses(board)["T02"] == "Done"
    board.tickets[7].status = "In review"
    bs.on_branch_created(board, "t06-more", "branch")
    assert statuses(board)["T06"] == "In review"


# ---- pull request events -------------------------------------------------------------------------

def test_opened_pr_moves_ticket_to_in_review():
    for start in ("Backlog", "Ready", "In progress"):
        board = chain()
        board.tickets[7].status = start
        bs.on_pull_request(board, "opened", pr())
        assert statuses(board)["T06"] == "In review", start


def test_draft_pr_keeps_ticket_in_progress_until_ready_for_review():
    board = chain()
    bs.on_pull_request(board, "opened", pr(draft=True))
    assert statuses(board)["T06"] == "In progress"
    bs.on_pull_request(board, "ready_for_review", pr())
    assert statuses(board)["T06"] == "In review"
    bs.on_pull_request(board, "converted_to_draft", pr(draft=True))
    assert statuses(board)["T06"] == "In progress"


def test_closing_a_pr_without_merging_falls_back_to_in_progress():
    board = chain()
    bs.on_pull_request(board, "opened", pr())
    bs.on_pull_request(board, "closed", pr(merged=False))
    assert statuses(board)["T06"] == "In progress"
    bs.on_pull_request(board, "reopened", pr())
    assert statuses(board)["T06"] == "In review"


def test_merged_pr_marks_done_and_unlocks_dependents():
    board = chain()
    bs.on_pull_request(board, "opened", pr())
    bs.on_pull_request(board, "closed", pr(merged=True))
    result = statuses(board)
    assert result["T06"] == "Done"
    assert result["T11"] == "Ready"  # needed T04 + T06, both done now
    assert result["T08"] == "Backlog"  # still waits for T07
    assert result["T29"] == "Backlog"  # no dependencies: never started automatically


def test_unlock_needs_all_dependencies_done():
    board = chain()
    board.tickets[5].status = "In review"  # T04 not done
    bs.on_pull_request(board, "closed", pr(merged=True))
    assert statuses(board)["T11"] == "Backlog"


def test_unlock_posts_a_comment_mentioning_the_owner():
    comments = []

    class Recording(bs.Board):
        def comment(self, ticket, text):
            comments.append((ticket.tid, text))

    board = Recording(list(chain().tickets.values()))
    bs.on_pull_request(board, "closed", pr(merged=True))
    assert [c[0] for c in comments] == ["T11"]
    assert "@dev12" in comments[0][1] and "T06 (#7)" in comments[0][1] and "t11-" in comments[0][1]


def test_dependency_on_unknown_ticket_blocks():
    board = make_board({1: ("T01", [], "Done", "CLOSED"), 2: ("T02", [1, 999], "Backlog")})
    bs.unlock(board)
    assert statuses(board)["T02"] == "Backlog"


def test_refs_pr_never_moves_a_card():
    board = chain()
    before = statuses(board)
    for action in ("opened", "ready_for_review", "closed"):
        bs.on_pull_request(board, action, pr(body="Refs #7", merged=(action == "closed")))
    assert statuses(board) == before


def test_pr_without_ticket_or_for_unknown_issue_changes_nothing():
    board = chain()
    before = statuses(board)
    bs.on_pull_request(board, "closed", pr(body="chore: update progress", merged=True))
    bs.on_pull_request(board, "opened", pr(body="Closes #4242"))
    assert statuses(board) == before


def test_done_ticket_is_not_pulled_back_by_a_later_pr():
    board = chain()
    bs.on_pull_request(board, "opened", pr(body="Closes #3"))  # T02 is Done
    bs.on_pull_request(board, "closed", pr(body="Closes #3", merged=False))
    assert statuses(board)["T02"] == "Done"


def test_one_pr_can_close_several_tickets():
    board = chain()
    bs.on_pull_request(board, "opened", pr(body="Closes #7\nCloses #8"))
    assert statuses(board)["T06"] == statuses(board)["T07"] == "In review"


def test_merging_a_ticket_that_is_already_done_still_unlocks_dependents():
    """The board's built-in "Pull request merged" workflow sets Done before the script runs."""
    board = chain()
    board.tickets[7].status = "Done"  # already moved by the built-in workflow
    bs.on_pull_request(board, "closed", pr(merged=True))
    assert statuses(board)["T06"] == "Done"
    assert statuses(board)["T11"] == "Ready"  # T04 and T06 are done


def test_closing_without_merging_never_unlocks():
    board = chain()
    board.tickets[7].status = "Done"
    bs.on_pull_request(board, "closed", pr(merged=False))
    assert statuses(board)["T11"] == "Backlog"


# ---- reconcile -----------------------------------------------------------------------------------

def test_reconcile_repairs_everything_from_real_state():
    board = chain()
    board.tickets[8].status = "In review"        # no open PR -> back to In progress
    board.tickets[7].status = "Ready"            # has an open PR -> In review
    board.tickets[3].status = "In progress"      # issue closed -> Done
    bs.reconcile(board, [{"number": 41, "body": "Closes #7", "isDraft": False}])
    result = statuses(board)
    assert result["T06"] == "In review"
    assert result["T07"] == "In progress"
    assert result["T02"] == "Done"


def test_reconcile_draft_pr_is_in_progress_and_unlocks_after_done():
    board = chain()
    board.tickets[7].status = "Done"
    board.tickets[7].state = "CLOSED"
    bs.reconcile(board, [{"number": 50, "body": "Closes #9", "isDraft": True}])
    result = statuses(board)
    assert result["T11"] == "Ready"
    assert result["T08"] == "In progress"


def test_reconcile_is_idempotent():
    board = chain()
    prs = [{"number": 41, "body": "Closes #7", "isDraft": False}]
    bs.reconcile(board, prs)
    board.log.clear()
    bs.reconcile(board, prs)
    assert board.log == []
