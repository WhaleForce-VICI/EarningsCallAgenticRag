#!/usr/bin/env python3
"""
Generate a lightweight Knowledge Graph visualization from sample_data_results.csv.

The script parses the `parsed_and_analyzed_facts` column, builds a graph where:
  • Company-quarter nodes link to fact nodes.
  • Fact nodes link to value and reason nodes.
  • Fact nodes also connect to helper tools that produced them.

The output is an interactive HTML file rendered with PyVis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd
from pyvis.network import Network


def parse_items(cell: str | float) -> list[dict]:
    """Parse the JSON stored in `parsed_and_analyzed_facts`."""
    if not isinstance(cell, str) or not cell.strip():
        return []
    try:
        data = json.loads(cell)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def add_fact_nodes(
    net: Network,
    ticker: str,
    quarter: str,
    facts: Iterable[dict],
) -> None:
    """Add nodes/edges for a ticker-quarter chunk of facts."""
    company_id = f"{ticker}_{quarter}"
    if company_id not in net.node_ids:
        net.add_node(
            company_id,
            label=f"{ticker}\n{quarter}",
            shape="ellipse",
            color="#2E86AB",
        )

    for idx, fact in enumerate(facts):
        metric = fact.get("metric") or "Unknown Metric"
        fact_type = fact.get("type") or "Fact"
        fact_id = f"{company_id}_fact_{idx}"
        net.add_node(
            fact_id,
            label=f"{metric}\n({fact_type})",
            shape="box",
            color="#F1C40F",
        )
        net.add_edge(company_id, fact_id, title="reports")

        value = fact.get("value")
        if value:
            value_id = f"{fact_id}_value"
            net.add_node(
                value_id,
                label=f"Value:\n{value}",
                shape="note",
                color="#27AE60",
            )
            net.add_edge(fact_id, value_id, title="has value")

        reason = fact.get("reason")
        if reason:
            reason_id = f"{fact_id}_reason"
            net.add_node(
                reason_id,
                label=f"Reason:\n{reason}",
                shape="note",
                color="#E67E22",
            )
            net.add_edge(fact_id, reason_id, title="explained by")

        for tool in fact.get("tools") or []:
            tool_id = f"tool_{tool}"
            if tool_id not in net.node_ids:
                net.add_node(
                    tool_id,
                    label=tool,
                    shape="hexagon",
                    color="#9B59B6",
                )
            net.add_edge(tool_id, fact_id, title="contributed")


def build_graph(csv_path: Path, output_path: Path) -> None:
    df = pd.read_csv(csv_path)
    net = Network(
        height="100%",
        width="100%",
        notebook=False,
        bgcolor="#FFFFFF",
        font_color="#2C3E50",
        cdn_resources="in_line",
    )
    net.prep_notebook()
    net.barnes_hut()

    for _, row in df.iterrows():
        facts = parse_items(row.get("parsed_and_analyzed_facts", ""))
        if not facts:
            continue
        add_fact_nodes(net, str(row["ticker"]), str(row["quarter"]), facts)

    if not net.nodes:
        raise SystemExit("No facts found to visualize.")

    net.show(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a PyVis KG visualization from sample_data_results.csv",
    )
    parser.add_argument(
        "--input",
        default="sample_data_results.csv",
        type=Path,
        help="CSV file with parsed_and_analyzed_facts (default: sample_data_results.csv)",
    )
    parser.add_argument(
        "--output",
        default="kg_graph.html",
        type=Path,
        help="Output HTML path (default: kg_graph.html)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input CSV not found: {args.input}")

    build_graph(args.input, args.output)
    print(f"✅ Knowledge graph saved to {args.output}")


if __name__ == "__main__":
    main()
