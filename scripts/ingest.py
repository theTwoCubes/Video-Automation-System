#!/usr/bin/env python3
"""
Ingest a knowledge source (PDF, URL, or markdown directory).

Usage:
  python scripts/ingest.py --source path/to/book.pdf --name "C Programming Book" --topic "C"
  python scripts/ingest.py --source https://learncpp.com --name "LearnCpp" --type url --topic "C++"
  python scripts/ingest.py --source ./docs/ --name "Python Docs" --type markdown_dir --topic "Python"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import typer
from rich.console import Console
from rich.panel import Panel
from db.database import init_db
from services.knowledge.ingestion import KnowledgeIngestionService

app = typer.Typer()
console = Console()


@app.command()
def main(
    source: str = typer.Option(..., "--source", help="File path or URL"),
    name: str = typer.Option(..., "--name", help="Human-readable name for this source"),
    topic: str = typer.Option(..., "--topic", help="Primary topic (e.g. C, Python, Docker)"),
    source_type: str = typer.Option("pdf", "--type", help="pdf | url | markdown_dir"),
    tags: str = typer.Option("", "--tags", help="Comma-separated additional tags"),
):
    init_db()
    console.print(Panel(f"[bold green]Ingesting:[/] {name}", title="theTwoCubes Ingestion"))

    tag_list = [topic.lower()] + [t.strip().lower() for t in tags.split(",") if t.strip()]

    service = KnowledgeIngestionService()
    source_id = service.ingest(
        name=name,
        source_type=source_type,
        path_or_url=source,
        topic_tags=tag_list,
    )

    console.print(f"\n[bold green]Done![/] Source ID: [cyan]{source_id}[/]")
    console.print(f"Use this ID when generating the curriculum:\n  python scripts/generate_curriculum.py --source-id {source_id} --topic \"{topic}\"")


if __name__ == "__main__":
    app()
