"""CLI entry point — thin wrapper around the pipeline orchestrator.

Usage:
    python -m src.cli --input sample_inputs/ --output output.json
    python -m src.cli --input sample_inputs/ --config configs/custom_config.json
    python -m src.cli --input file1.json file2.csv resume.txt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from src.pipeline.orchestrator import PipelineResult, load_config, run_pipeline
from src.utils.logger import get_logger

logger = get_logger(__name__)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--input", "-i",
    "input_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Input files or directories containing source data.",
)
@click.option(
    "--config", "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to runtime output config JSON. If omitted, emits full canonical schema.",
)
@click.option(
    "--output", "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write output to this file instead of stdout.",
)
@click.option(
    "--pretty/--compact",
    default=True,
    help="Pretty-print JSON output (default: pretty).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging.",
)
def main(
    input_paths: tuple[Path, ...],
    config_path: Path | None,
    output_path: Path | None,
    pretty: bool,
    verbose: bool,
) -> None:
    """Eightfold Candidate Profile Transformer.

    Transforms messy multi-source candidate data into one clean,
    canonical profile with provenance and confidence scoring.
    """
    import os
    if verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"

    click.echo("╔══════════════════════════════════════════════╗", err=True)
    click.echo("║  TalentFlow Candidate Profile Transformer    ║", err=True)
    click.echo("╚══════════════════════════════════════════════╝", err=True)
    click.echo("", err=True)

    # Load config if provided
    config = None
    if config_path:
        click.echo(f"📋 Loading config: {config_path}", err=True)
        config = load_config(config_path)
        if config is None:
            click.echo("❌ Failed to load config file", err=True)
            sys.exit(1)
        click.echo(
            f"   → {len(config.fields)} fields, "
            f"on_missing={config.on_missing}, "
            f"confidence={'on' if config.include_confidence else 'off'}",
            err=True,
        )

    # Show input summary
    click.echo(f"📂 Input paths: {', '.join(str(p) for p in input_paths)}", err=True)

    # Run pipeline
    click.echo("", err=True)
    click.echo("🔄 Running pipeline...", err=True)

    result: PipelineResult = run_pipeline(list(input_paths), config)

    # Report results
    click.echo("", err=True)
    profile_count = len(result.profiles)
    click.echo(f"✅ Pipeline complete: {profile_count} profile(s) generated", err=True)

    if result.warnings:
        click.echo(f"⚠️  {len(result.warnings)} warning(s):", err=True)
        for w in result.warnings[:10]:
            click.echo(f"   - {w}", err=True)
        if len(result.warnings) > 10:
            click.echo(f"   ... and {len(result.warnings) - 10} more", err=True)

    # Output
    indent = 2 if pretty else None
    output_json = result.to_json(indent=indent)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        click.echo(f"📄 Output written to: {output_path}", err=True)
    else:
        click.echo("", err=True)
        click.echo("─── Output ───", err=True)
        click.echo(output_json)

    # Summary
    if result.profiles:
        click.echo("", err=True)
        click.echo("─── Summary ───", err=True)
        for p in result.profiles:
            click.echo(
                f"  • {p.full_name or '(unknown)'} "
                f"[{p.candidate_id}] "
                f"confidence={p.overall_confidence:.2f} "
                f"emails={len(p.emails)} "
                f"skills={len(p.skills)} "
                f"experience={len(p.experience)} "
                f"education={len(p.education)}",
                err=True,
            )


if __name__ == "__main__":
    main()
