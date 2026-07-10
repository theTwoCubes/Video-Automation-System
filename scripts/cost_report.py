#!/usr/bin/env python3
"""
Cost report: show total API token usage and cost from SQLite.

Usage:
  python scripts/cost_report.py
  python scripts/cost_report.py --clear
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer()
console = Console()


@app.command()
def main(clear: bool = typer.Option(False, "--clear", help="Clear usage log after reporting")):
    from db.usage_log import get_usage_report, _get_conn

    report = get_usage_report()

    table = Table(title="theTwoCubes - API Cost Report", box=box.ROUNDED)
    table.add_column("Model", style="cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_column("Think Tokens", justify="right")
    table.add_column("Cost (USD)", justify="right", style="yellow")
    table.add_column("Cost (INR)", justify="right", style="green")

    for m in report["models"]:
        table.add_row(
            m["model"],
            str(m["calls"]),
            f"{m['input_tokens']:,}",
            f"{m['output_tokens']:,}",
            f"{m['thinking_tokens']:,}",
            f"${m['cost_usd']:.4f}",
            f"₹{m['cost_inr']:.2f}",
        )

    console.print(table)
    console.print(f"\n[bold]TOTAL:[/bold] [yellow]${report['total_cost_usd']:.4f}[/] | [green]₹{report['total_cost_inr']:.2f}[/]")

    if clear:
        conn = _get_conn()
        conn.execute("DELETE FROM usage_log")
        conn.commit()
        conn.close()
        console.print("[dim]Usage log cleared.[/]")


if __name__ == "__main__":
    app()
