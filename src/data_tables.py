"""
Centralized data-table storage for the parking garage analyzer.

Provides a lightweight SQLite-backed repository that stores every scenario as a
set of normalized tables:
    - projects
    - soil_layers
    - elements
    - quantities
    - unit_costs
    - cost_items
    - diagnostics

The tables are designed for deterministic, auditable pipelines. All geometry,
structural, and cost passes append rows into these tables so downstream
reporting and validation can operate with simple SQL.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import enum


DEFAULT_DB_URL_ENV = "PGA_DATABASE_URL"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _to_json(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, str):
        return value
    def _default(o: Any):
        # Convert Enum values to their underlying value (usually a string)
        if isinstance(o, enum.Enum):
            return o.value
        # Dataclasses or objects with a dict-like representation
        if hasattr(o, "to_dict") and callable(getattr(o, "to_dict")):
            return o.to_dict()
        if hasattr(o, "__dict__"):
            return {k: v for k, v in o.__dict__.items() if not k.startswith("_")}
        # Fallback to string to avoid serialization crashes while preserving audit trail
        return str(o)
    return json.dumps(value, default=_default, separators=(",", ":"), sort_keys=True)


@dataclass
class ProjectRecord:
    project_id: str
    created_at: str
    inputs: Dict[str, Any]


class DataTables:
    """
    Thin wrapper around SQLite for managing scenario tables.

    Uses an in-memory database by default. Set `db_path` to a filesystem path to
    persist tables locally. Postgres/Neon can be supported in the future by
    swapping this implementation for an equivalent SQL interface.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.conn = sqlite3.connect(db_path)
        else:
            self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    # --------------------------------------------------------------------- schema
    def _initialize_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                inputs_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS soil_layers (
                project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                layer_index INTEGER NOT NULL,
                depth_start_ft REAL NOT NULL,
                depth_end_ft REAL NOT NULL,
                soil_type TEXT NOT NULL,
                bearing_capacity_psf REAL NOT NULL,
                angle_of_repose_deg REAL NOT NULL,
                excavation_method TEXT NOT NULL,
                unit_cost_per_cy REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (project_id, layer_index)
            );

            CREATE TABLE IF NOT EXISTS elements (
                element_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                element_type TEXT NOT NULL,
                name TEXT,
                level_index INTEGER,
                parent_element_id TEXT REFERENCES elements(element_id),
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quantities (
                quantity_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                element_id TEXT NOT NULL REFERENCES elements(element_id) ON DELETE CASCADE,
                measure TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                source_pass TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS unit_costs (
                unit_cost_key TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                unit TEXT NOT NULL,
                category TEXT NOT NULL,
                value REAL NOT NULL,
                source TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cost_items (
                cost_item_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                quantity_id TEXT REFERENCES quantities(quantity_id),
                element_id TEXT REFERENCES elements(element_id),
                unit_cost_key TEXT REFERENCES unit_costs(unit_cost_key),
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                unit TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                source_pass TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS diagnostics (
                diagnostic_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                scope TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                detail_json TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    # --------------------------------------------------------------------- helpers
    def reset_project(self, project_id: str) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        self.conn.commit()

    def create_project(self, inputs: Dict[str, Any]) -> ProjectRecord:
        project_id = inputs.get("project_id") or str(uuid.uuid4())
        created_at = _utcnow_iso()
        payload = _to_json(inputs)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO projects (project_id, created_at, inputs_json) VALUES (?, ?, ?)",
            (project_id, created_at, payload),
        )
        self.conn.commit()
        return ProjectRecord(project_id=project_id, created_at=created_at, inputs=inputs)

    def add_soil_layers(self, project_id: str, layers: Iterable[Dict[str, Any]]) -> None:
        cur = self.conn.cursor()
        for index, layer in enumerate(layers):
            cur.execute(
                """
                INSERT INTO soil_layers (
                    project_id, layer_index, depth_start_ft, depth_end_ft,
                    soil_type, bearing_capacity_psf, angle_of_repose_deg,
                    excavation_method, unit_cost_per_cy, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    index,
                    layer["depth_start_ft"],
                    layer["depth_end_ft"],
                    layer["soil_type"],
                    layer["bearing_capacity_psf"],
                    layer["angle_of_repose_deg"],
                    layer["excavation_method"],
                    layer["unit_cost_per_cy"],
                    _to_json(layer.get("metadata", {})),
                ),
            )
        self.conn.commit()

    def add_element(
        self,
        project_id: str,
        element_type: str,
        name: Optional[str] = None,
        *,
        level_index: Optional[int] = None,
        parent_element_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        element_id = str(uuid.uuid4())
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO elements (
                element_id, project_id, element_type, name,
                level_index, parent_element_id, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                element_id,
                project_id,
                element_type,
                name,
                level_index,
                parent_element_id,
                _to_json(metadata),
            ),
        )
        self.conn.commit()
        return element_id

    def add_quantity(
        self,
        project_id: str,
        element_id: str,
        measure: str,
        value: float,
        unit: str,
        *,
        source_pass: str,
        notes: Optional[str] = None,
    ) -> str:
        quantity_id = str(uuid.uuid4())
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO quantities (
                quantity_id, project_id, element_id,
                measure, value, unit, source_pass, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quantity_id,
                project_id,
                element_id,
                measure,
                value,
                unit,
                source_pass,
                notes,
            ),
        )
        self.conn.commit()
        return quantity_id

    def ensure_unit_costs(self, cost_database: Dict[str, Any]) -> None:
        """
        Populate unit_costs table from the JSON cost database.

        This flattens the nested structure into semantic keys so cost lookups can
        be performed with simple joins.
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM unit_costs")

        def infer_unit(key: str) -> str:
            if key.endswith("_cy"):
                return "CY"
            if key.endswith("_sf"):
                return "SF"
            if key.endswith("_lf"):
                return "LF"
            if key.endswith("_ea"):
                return "EA"
            if key.endswith("_ls"):
                return "LS"
            if key.endswith("_per_month"):
                return "PER_MONTH"
            if key.endswith("_percentage") or key.endswith("_pct"):
                return "FACTOR"
            if key.endswith("_per_stall"):
                return "PER_STALL"
            if key.endswith("_per_sf"):
                return "PER_SF"
            if key.endswith("_per_cy"):
                return "PER_CY"
            if key.endswith("_per_lb"):
                return "PER_LB"
            if key.endswith("_lbs"):
                return "LB"
            if key.endswith("_lbs_per_sf"):
                return "LB_PER_SF"
            if key.endswith("_lbs_per_cy_concrete"):
                return "LB_PER_CY"
            if key.endswith("_cost"):
                return "USD"
            if key.endswith("_percentage"):
                return "FACTOR"
            if key.endswith("_per_stop"):
                return "PER_STOP"
            if key.endswith("_per_flight"):
                return "PER_FLIGHT"
            return "USD"

        def add_cost(semantic_key: str, category: str, key: str, value: Any, source: str) -> None:
            if not isinstance(value, (int, float)):
                return
            if semantic_key.startswith("unit_costs."):
                semantic_key = semantic_key[len("unit_costs.") :]
            unit = infer_unit(key)
            cur.execute(
                """
                INSERT INTO unit_costs (
                    unit_cost_key, description, unit, category, value, source
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    semantic_key,
                    key.replace("_", " ").title(),
                    unit,
                    category,
                    float(value),
                    source,
                ),
            )

        def flatten(section: Dict[str, Any], prefix: str, category_hint: str) -> None:
            for key, value in section.items():
                semantic_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    next_category = key
                    flatten(value, semantic_key, next_category)
                else:
                    add_cost(semantic_key, category_hint, key, value, prefix or category_hint)

        for category, section in cost_database.items():
            if isinstance(section, dict):
                flatten(section, category, category)

        self.conn.commit()

    def add_cost_item(
        self,
        project_id: str,
        *,
        quantity_id: Optional[str],
        element_id: Optional[str],
        unit_cost_key: str,
        category: str,
        description: str,
        unit: str,
        quantity: float,
        unit_cost: float,
        source_pass: str,
        notes: Optional[str] = None,
    ) -> str:
        cost_item_id = str(uuid.uuid4())
        total_cost = quantity * unit_cost
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO cost_items (
                cost_item_id, project_id, quantity_id, element_id, unit_cost_key,
                category, description, unit, quantity, unit_cost, total_cost,
                source_pass, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cost_item_id,
                project_id,
                quantity_id,
                element_id,
                unit_cost_key,
                category,
                description,
                unit,
                quantity,
                unit_cost,
                total_cost,
                source_pass,
                notes,
            ),
        )
        self.conn.commit()
        return cost_item_id

    def add_diagnostic(
        self,
        project_id: str,
        *,
        scope: str,
        level: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        diagnostic_id = str(uuid.uuid4())
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO diagnostics (
                diagnostic_id, project_id, scope, level, message, detail_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                diagnostic_id,
                project_id,
                scope,
                level,
                message,
                _to_json(detail or {}),
            ),
        )
        self.conn.commit()
        return diagnostic_id

    # --------------------------------------------------------------------- fetch
    def fetch_dataframe(self, table: str) -> pd.DataFrame:
        df = pd.read_sql_query(f"SELECT * FROM {table}", self.conn)
        return df

    def close(self) -> None:
        self.conn.close()


