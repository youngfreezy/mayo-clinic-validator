"""
Rules module — Neo4j graph-based rule store with structured JSON fallback.

Architecture:
  1. Primary:  Neo4j Aura (cloud graph DB) stores rules as nodes with
               EVALUATED_BY, APPLIES_TO, DEPENDS_ON, BELONGS_TO relationships.
  2. Fallback: backend/data/validation_rules.json is loaded when Neo4j
               is unavailable (no credentials, connection error, etc.).

Usage:
  from rules.loader import get_rules_for_agent
  rules = await get_rules_for_agent("metadata", content_type="standard")
"""
