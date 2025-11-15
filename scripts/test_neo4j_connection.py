#!/usr/bin/env python3
"""
Quick Neo4j connectivity check.

Reads credentials (default: credentials.json), opens a driver, runs a simple
read query, and reports cluster info. Fails loud if authentication or network
is misconfigured.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError


def load_credentials(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Credentials file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}") from exc


def test_connection(creds: dict) -> dict:
    driver = GraphDatabase.driver(
        creds["neo4j_uri"], auth=(creds["neo4j_username"], creds["neo4j_password"])
    )
    try:
        with driver.session() as session:
            info = session.run(
                "CALL db.info()"
            ).single()
            if info is None:
                raise RuntimeError("db.info() returned no data")
            info_dict = dict(info.items())
            ping = session.run("RETURN 1 AS ok").single()
            if ping is None or ping.get("ok") != 1:
                raise RuntimeError("Ping query failed")
            components = fetch_components(session)
            cluster = fetch_cluster_state(session)
            info_dict["components"] = components
            if cluster:
                info_dict["cluster"] = cluster
            return info_dict
    finally:
        driver.close()


def fetch_components(session):
    """Return dbms.components() output (best-effort)."""
    try:
        recs = session.run(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        ).data()
        return recs
    except Neo4jError as exc:
        print(f"⚠️  Unable to fetch components: {exc}")
        return []


def fetch_cluster_state(session):
    """Return cluster overview when available (Aura free tier returns nothing)."""
    try:
        recs = session.run("CALL dbms.cluster.overview()").data()
        return recs
    except Neo4jError:
        return []


def main():
    parser = argparse.ArgumentParser(description="Test Neo4j database connectivity.")
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("credentials.json"),
        help="Path to credentials JSON (default: credentials.json)",
    )
    args = parser.parse_args()

    try:
        creds = load_credentials(args.credentials)
    except Exception as exc:
        raise SystemExit(f"❌ Failed to load credentials: {exc}")

    missing = [k for k in ("neo4j_uri", "neo4j_username", "neo4j_password") if k not in creds]
    if missing:
        raise SystemExit(f"❌ Missing keys in credentials: {', '.join(missing)}")

    try:
        info = test_connection(creds)
    except Neo4jError as exc:
        raise SystemExit(f"❌ Neo4j error: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"❌ Connection test failed: {exc}") from exc

    print("✅ Successfully connected to Neo4j.")
    name = info.get("name") or info.get("databaseName") or "unknown"
    version = info.get("version") or info.get("dbmsVersion") or "unknown"
    role = info.get("role") or info.get("databaseRole") or "unknown"
    state = info.get("state") or info.get("currentStatus") or "unknown"
    address = info.get("address") or info.get("serverAddress") or "n/a"

    print(
        f"Database: {name} | Version: {version} | Role: {role} | "
        f"State: {state} | Address: {address}"
    )

    components = info.get("components", [])
    if components:
        print("\nComponents:")
        for comp in components:
            versions = ", ".join(comp.get("versions", []) or [])
            print(f"  - {comp.get('name')} [{comp.get('edition')}]: {versions}")
    else:
        print("\nComponents: unavailable")

    cluster_info = info.get("cluster", [])
    if cluster_info:
        print("\nCluster Overview:")
        for node in cluster_info:
            print(f"  - {node}")


if __name__ == "__main__":
    main()
