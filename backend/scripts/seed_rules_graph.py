#!/usr/bin/env python3
"""
Seed the Neo4j rules graph from validation_rules.json.

Usage:
  python scripts/seed_rules_graph.py

Reads NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD from .env.
Idempotent — safe to run multiple times (uses MERGE, not CREATE).
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from rules.graph_store import seed_rules, verify_connection, close_driver


async def main() -> None:
    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    password = settings.NEO4J_PASSWORD

    if not uri or not user or not password:
        print("ERROR: NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set in .env")
        print("       Get free credentials at https://neo4j.com/cloud/aura-free/")
        sys.exit(1)

    print(f"Connecting to Neo4j at {uri} ...")
    if not await verify_connection(uri, user, password):
        print("ERROR: Could not connect to Neo4j. Check URI and credentials.")
        await close_driver()
        sys.exit(1)
    print("Connected.")

    # Load rules JSON
    rules_path = Path(__file__).resolve().parent.parent / "data" / "validation_rules.json"
    with open(rules_path) as f:
        rules_data = json.load(f)

    print(f"Seeding rules v{rules_data.get('version', '?')} ...")
    stats = await seed_rules(uri, user, password, rules_data)

    print(f"Done! Seeded:")
    print(f"  Agents:       {stats['agents']}")
    print(f"  Rules:        {stats['rules']}")
    print(f"  Dependencies: {stats['dependencies']}")

    await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
