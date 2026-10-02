"""Refresh, commit and push profile cards from a clean Linux server checkout."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
GENERATED = [
    "README.md",
    *[f"WebCode/assets/images/{name}.svg" for name in (
        "contributions", "repository", "repository-pqsecure", "repository-agentarmor",
        "profile-overview", "profile-stats", "profile-languages", "profile-stats-row",
    )],
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def refresh() -> None:
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Checkout has uncommitted files; resolve them before retrying.")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    remote = git("config", f"branch.{branch}.remote")
    target = git("config", f"branch.{branch}.merge")
    if remote == "." or not target.startswith("refs/heads/"):
        raise RuntimeError("A remote tracking branch is required.")
    git("config", "user.name")
    git("config", "user.email")
    git("fetch", remote)
    # Refuse to publish any pre-existing local commits automatically.
    if git("rev-list", "@{upstream}..HEAD"):
        raise RuntimeError("Unpushed local commits found; inspect and push them manually first.")
    git("pull", "--ff-only", "--no-rebase", remote, target)
    subprocess.run([sys.executable, str(ROOT / "WebCode/update_contributions.py")],
                   cwd=ROOT, check=True, timeout=900)
    git("add", "--", *GENERATED)
    if not git("diff", "--cached", "--name-only"):
        print("No changes; no commit needed.", flush=True)
        return
    git("commit", "-m", "chore: refresh GitHub profile statistics")
    # Normal push only: a concurrent remote update fails safely without rewriting history.
    git("push", remote, f"HEAD:{target}")
    print("Profile statistics committed and pushed.", flush=True)


def main() -> None:
    import fcntl  # Linux server only; no third-party dependencies.
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=20")
    lock_path = Path(git("rev-parse", "--absolute-git-dir")) / "profile-refresh.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another profile refresh is running; skipped.", flush=True)
            return
        refresh()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
