"""ct — Cortical-Transfer CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cortical_transfer import store
from cortical_transfer.integrity import load_pack, verify_pack
from cortical_transfer.schema import SemanticNode

app = typer.Typer(no_args_is_help=True, add_completion=False)

ProfileOpt = Annotated[str, typer.Option("--profile", "-p", help="Memory profile name")]


@app.command()
def init(profile: ProfileOpt = "default") -> None:
    """Create a new Git-versioned memory profile."""
    path = store.init_profile(profile)
    typer.echo(f"initialized profile '{profile}' at {path}")


def _print_nodes(title: str, nodes: list[SemanticNode]) -> None:
    typer.echo(f"\n== {title} ({len(nodes)}) ==")
    for n in sorted(nodes, key=lambda n: -n.salience):
        mark = " [superseded]" if n.superseded_by else ""
        tags = f"  #{' #'.join(n.tags)}" if n.tags else ""
        typer.echo(f"  ({n.salience:.2f}) {n.text}{tags}{mark}")


@app.command()
def inspect(profile: ProfileOpt = "default") -> None:
    """Pretty-print the current memory."""
    pack = load_pack(store.profile_path(profile))
    m = pack.manifest
    typer.echo(f"MemPack {m.format_version} — updated {m.updated_at:%Y-%m-%d %H:%M} UTC")
    _print_nodes("identity", pack.identity)
    _print_nodes("episodes", pack.episodes)
    _print_nodes("open threads", pack.threads)
    typer.echo(f"\n== style ==\n{pack.style.strip() or '(empty)'}")


@app.command()
def diff(
    rev_a: Annotated[str, typer.Argument(help="older revision")] = "HEAD~1",
    rev_b: Annotated[str, typer.Argument(help="newer revision")] = "HEAD",
    profile: ProfileOpt = "default",
) -> None:
    """Human-readable memory changes between two revisions."""
    lines = store.diff(profile, rev_a, rev_b)
    typer.echo("\n".join(lines) if lines else "no memory changes")


@app.command()
def log(profile: ProfileOpt = "default") -> None:
    """Memory history, newest first."""
    for sha, date, msg in store.log(profile):
        typer.echo(f"{sha}  {date}  {msg}")


@app.command()
def checkout(rev: str, profile: ProfileOpt = "default") -> None:
    """Restore a previous memory state (as a new commit)."""
    sha = store.checkout(profile, rev)
    typer.echo(f"restored state from {rev} as {sha[:8]}")


@app.command()
def verify(
    path: Annotated[Path | None, typer.Argument(help="pack dir (default: profile)")] = None,
    profile: ProfileOpt = "default",
) -> None:
    """Verify the SHA-256 integrity manifest."""
    target = path or store.profile_path(profile)
    errors = verify_pack(target)
    if errors:
        for e in errors:
            typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"ok — {target} verifies")


if __name__ == "__main__":
    app()
