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


@app.command()
def extract(
    history: Annotated[Path, typer.Argument(help="chat history JSONL", exists=True)],
    profile: ProfileOpt = "default",
) -> None:
    """Extract a MemPack from chat history and commit it to the profile."""
    import logging

    from cortical_transfer.adapters.base import get_adapter
    from cortical_transfer.extract.pipeline import extract as run_extract

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    adapter = get_adapter()
    pack = run_extract(history, adapter)
    sha = store.commit_pack(pack, profile, f"feat: extract from {history.name}")
    n = len(pack.all_nodes())
    typer.echo(f"extracted {n} nodes -> commit {sha[:8]}")


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
def inject(
    budget: Annotated[int, typer.Option(help="token budget for the context block")] = 2000,
    query: Annotated[str | None, typer.Option(help="topic for RAG retrieval (optional)")] = None,
    profile: ProfileOpt = "default",
) -> None:
    """Print a portable, token-budgeted context block to stdout."""
    from cortical_transfer.inject import build_context

    path = store.profile_path(profile)
    typer.echo(build_context(load_pack(path), budget_tokens=budget, query=query, pack_path=path))


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


@app.command()
def export(
    dest: Annotated[Path, typer.Argument(help="output .mempack file")],
    profile: ProfileOpt = "default",
) -> None:
    """Export the profile as a portable .mempack file."""
    typer.echo(f"exported {store.export_pack(profile, dest)}")


@app.command(name="import")
def import_(
    src: Annotated[Path, typer.Argument(help=".mempack file or pack directory", exists=True)],
    profile: ProfileOpt = "default",
    force: Annotated[bool, typer.Option(help="import even if integrity check fails")] = False,
) -> None:
    """Import a MemPack into a profile (verified + sanitized)."""
    from cortical_transfer.integrity import IntegrityError

    try:
        sha = store.import_pack(src, profile, force=force)
    except IntegrityError as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"imported into '{profile}' as commit {sha[:8]}")


mcp_app = typer.Typer(no_args_is_help=True)
app.add_typer(mcp_app, name="mcp", help="MCP server commands")


@mcp_app.command()
def serve() -> None:
    """Run the MCP server on stdio."""
    from cortical_transfer.mcp_server import serve as run_serve

    run_serve()


if __name__ == "__main__":
    app()
