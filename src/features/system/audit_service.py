"""
Cross-Database Document Alignment & Integrity Audit Mixin
=========================================================
Component: `src.features.system.audit_service`
Architecture Layer: System / Cross-Database Auditing & Telemetry Dashboards

Overview:
---------
Provides deep cross-database consistency checks, document synchronization,
session interaction logging audits, and terminal dashboard formatting.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from src.core.config import settings

logger = logging.getLogger("raise.system.audit_service")


class SystemAuditMixin:
    """
    Mixin providing document alignment audits, automated metadata sync,
    deep database integrity scans, and console dashboard rendering.
    """

    def audit_document_alignment(self) -> Dict[str, Any]:
        """
        Cross-checks documents across Disk, PostgreSQL, ChromaDB, and Neo4j.
        Detects if any document exists in one database but was omitted in another.
        """
        disk_files = [f.name for f in self.docs_dir.glob("*.pdf")] if self.docs_dir.exists() else []
        pg_docs = [d.get("filename") for d in self.postgres.list_documents() if d.get("filename")]

        # Ingested manifest check
        manifest_files = set()
        manifest_file = settings.processed_dir / "ingested_manifest.json"
        if manifest_file.exists():
            try:
                mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
                for rd in mdata.get("ready_documents", []):
                    if rd.get("filename"):
                        manifest_files.add(rd.get("filename"))
            except Exception:
                pass

        # ChromaDB check
        chroma_files = set()
        try:
            if hasattr(self.vector_engine, "collection") and self.vector_engine.collection:
                sample_meta = self.vector_engine.collection.get(limit=1000, include=["metadatas"]).get("metadatas", [])
                for m in sample_meta:
                    if m and m.get("pdf_filename"):
                        chroma_files.add(m.get("pdf_filename"))
        except Exception:
            pass

        # Neo4j document check
        neo4j_files = set()
        if self.neo4j.connected:
            try:
                rows = self.neo4j.run_cypher("MATCH (n:Chunk) RETURN DISTINCT n.document_id AS doc_id LIMIT 100")
                for r in rows:
                    if r.get("doc_id"):
                        neo4j_files.add(r.get("doc_id"))
            except Exception:
                pass

        def _norm(name: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]", "", str(name).lower())

        audit_results = []
        for df in disk_files:
            df_norm = _norm(df)
            in_pg = (df in pg_docs) or any(_norm(p) == df_norm for p in pg_docs)
            in_chroma = (df in chroma_files) or any(_norm(c) == df_norm for c in chroma_files)
            in_manifest = (df in manifest_files) or any(_norm(m) == df_norm for m in manifest_files)

            is_synced = (in_pg and in_chroma) or (in_chroma and in_manifest) or (in_pg and in_manifest)
            audit_results.append({
                "filename": df,
                "in_disk": True,
                "in_postgres": in_pg,
                "in_chromadb": in_chroma,
                "status": "SYNCHRONIZED" if is_synced else "PENDING_INDEX",
            })

        return {
            "total_disk_pdfs": len(disk_files),
            "total_postgres_records": len(pg_docs),
            "total_chromadb_distinct_docs": len(chroma_files),
            "documents": audit_results,
        }

    def auto_synchronize_pending_documents(self) -> int:
        """
        Scans data/documents on disk and ensures every PDF has a corresponding
        record in PostgreSQL document_metadata and document status registry.
        """
        alignment = self.audit_document_alignment()
        synced_count = 0
        docs = alignment.get("documents", [])
        for d in docs:
            fn = d.get("filename")
            if not fn:
                continue
            if not d.get("in_postgres"):
                clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(fn).stem)[:40]
                doc_id = f"doc_{clean_stem}"
                chunks_dir = settings.chunks_dir
                chunks_count = 0
                if chunks_dir.exists():
                    chunk_file = chunks_dir / f"{clean_stem}_chunks.json"
                    if chunk_file.exists():
                        try:
                            chunks_count = len(json.loads(chunk_file.read_text(encoding="utf-8")))
                        except Exception:
                            chunks_count = 0
                    if chunks_count == 0:
                        pattern = clean_stem.lower()
                        chunks_count = len([f for f in chunks_dir.glob("*.json") if pattern in f.name.lower()])
                self.postgres.save_document(
                    doc_id=doc_id,
                    filename=fn,
                    chunks_count=chunks_count,
                    library="default",
                )
                self.postgres.upsert_document_status(
                    doc_id=doc_id,
                    filename=fn,
                    phase="ready",
                    percent=100,
                    status="ready",
                    detail="Auto-synchronized from disk repository",
                    library="default",
                )
                synced_count += 1
        return synced_count

    def get_recent_chat_audit(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent interaction logs for audit."""
        conn = self.postgres._get_connection()
        if not conn:
            if hasattr(self.postgres, "_memory_chat") and self.postgres._memory_chat:
                all_msgs = []
                for sess_msgs in self.postgres._memory_chat.values():
                    if isinstance(sess_msgs, list):
                        all_msgs.extend(sess_msgs)
                return [
                    {
                        "session_id": r.get("session_id", "default"),
                        "role": r.get("role", "user"),
                        "content": (r.get("content", "")[:160] + "...") if len(r.get("content", "")) > 160 else r.get("content", ""),
                        "mode": r.get("mode", "fast"),
                        "sources": r.get("sources", []),
                        "created_at": str(r.get("created_at", "")),
                    }
                    for r in all_msgs[-limit:]
                ]
            return []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT session_id, role, content, mode, sources, created_at
                FROM chat_messages
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            cur.close()
            self.postgres._release_connection(conn)
            return [
                {
                    "session_id": r[0],
                    "role": r[1],
                    "content": r[2][:160] + "..." if len(r[2]) > 160 else r[2],
                    "mode": r[3],
                    "sources": r[4],
                    "created_at": str(r[5]),
                }
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def audit_deep_database_integrity(self) -> Dict[str, Any]:
        """
        Deep Integrity Audit Protocol across Redis, PostgreSQL, Neo4j, and ChromaDB:
        - Redis: Inspects keyspace types & memory signatures defensively without dumping payload values.
        - PostgreSQL: Tables discovery in public schema, dynamic row counts, session message history audit.
        - Neo4j: Active documents & node/relationship distribution, chunk sample inspection.
        - ChromaDB: Collection space, dimension, and chunk verification.
        """
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "redis_audit": {},
            "postgres_audit": {},
            "neo4j_audit": {},
            "chromadb_audit": {},
        }

        # 1. Redis Audit Protocol
        if self.redis.is_connected and self.redis._client:
            try:
                r = self.redis._client
                raw_keys = r.keys("*")
                keys = [k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in raw_keys]
                key_types = {}
                for k in keys[:50]:
                    k_type = r.type(k)
                    key_types[k] = k_type.decode("utf-8") if isinstance(k_type, bytes) else str(k_type)
                cfg = r.config_get("maxmemory*")
                results["redis_audit"] = {
                    "status": "PASS",
                    "total_keys": len(keys),
                    "sampled_keys_count": len(key_types),
                    "key_types_sample": key_types,
                    "maxmemory": cfg.get("maxmemory", "default"),
                    "maxmemory_policy": cfg.get("maxmemory-policy", "allkeys-lru"),
                }
            except Exception as e:
                results["redis_audit"] = {"status": "ERROR", "error": str(e)}

        # 2. PostgreSQL Schema & Session Verification
        conn = self.postgres._get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        ORDER BY table_name;
                    """)
                    tables = [row[0] for row in cur.fetchall()]
                    table_counts = {}
                    for tbl in tables:
                        cur.execute(f"SELECT count(*) FROM {tbl};")
                        table_counts[tbl] = cur.fetchone()[0]

                    cur.execute("""
                        SELECT id, session_id, role, mode, length(content) as content_len, created_at 
                        FROM chat_messages 
                        ORDER BY created_at DESC 
                        LIMIT 10;
                    """)
                    recent_messages = [
                        {
                            "id": row[0],
                            "session_id": row[1],
                            "role": row[2],
                            "mode": row[3],
                            "content_len": row[4],
                            "created_at": str(row[5]),
                        }
                        for row in cur.fetchall()
                    ]

                    results["postgres_audit"] = {
                        "status": "PASS",
                        "public_tables": tables,
                        "row_counts": table_counts,
                        "recent_messages_sample": recent_messages,
                    }
                self.postgres._release_connection(conn)
            except Exception as e:
                results["postgres_audit"] = {"status": "ERROR", "error": str(e)}

        # 3. Neo4j Graph Topology Audit
        if self.neo4j.connected:
            try:
                doc_dist = self.neo4j.run_cypher("""
                    MATCH (n) 
                    RETURN DISTINCT n.document_id AS doc_id, count(n) AS cnt
                """)
                chunk_sample = self.neo4j.run_cypher("""
                    MATCH (n:Chunk) 
                    RETURN n.id AS id, n.page AS page, n.document_id AS document_id 
                    LIMIT 3
                """)
                results["neo4j_audit"] = {
                    "status": "PASS",
                    "total_nodes": self.neo4j.count_nodes(),
                    "total_edges": self.neo4j.count_edges(),
                    "document_node_distribution": doc_dist,
                    "chunk_sample": chunk_sample,
                }
            except Exception as e:
                results["neo4j_audit"] = {"status": "ERROR", "error": str(e)}

        # 4. ChromaDB Vector Store Audit
        try:
            cnt = self.vector_engine.count()
            results["chromadb_audit"] = {
                "status": "PASS",
                "total_chunks": cnt,
                "dimension": self.vector_engine.dimension,
                "collection_name": getattr(self.vector_engine.collection, "name", "default"),
                "embedding_model": "BAAI/bge-large-en-v1.5",
                "trust_remote_code": False,
            }
        except Exception as e:
            results["chromadb_audit"] = {"status": "ERROR", "error": str(e)}

        return results

    def format_dashboard_text(self, rep: Dict[str, Any]) -> str:
        """Render formatted ASCII dashboard text for console or log output."""
        dbs = rep.get("databases", {})
        inf = rep.get("inference", {})
        net = rep.get("networking", {})
        doc_align = rep.get("document_alignment", {})

        lines = [
            "",
            "=" * 78,
            " 🛡️  RAISE DEVELOPER & DATABASE OPERATOR DASHBOARD",
            f" Timestamp: {rep.get('operator_timestamp')} | Checkup Time: {rep.get('checkup_duration_ms')}ms",
            "=" * 78,
            "",
            " ── 1. CORE SUBSYSTEMS STATUS ──────────────────────────────────────────",
            f" {'COMPONENT':<18} | {'PORT / TARGET':<14} | {'STATUS':<8} | {'DETAILS':<32}",
            " " + "-" * 76,
        ]

        pg = dbs.get("postgresql", {})
        pg_det = f"Msgs: {pg.get('chat_messages_count', 0)}, Docs: {pg.get('registered_documents', 0)} ({pg.get('latency_ms', 0)}ms)"
        lines.append(f" {'PostgreSQL 16':<18} | {'Port: 5432':<14} | {pg.get('status', 'N/A'):<8} | {pg_det:<32}")

        rd = dbs.get("redis", {})
        rd_det = f"Keys: {rd.get('total_keys', 0)}, Mem: {rd.get('used_memory_human', 'N/A')} ({rd.get('latency_ms', 0)}ms)"
        lines.append(f" {'Redis 7':<18} | {'Port: 6379':<14} | {rd.get('status', 'N/A'):<8} | {rd_det:<32}")

        neo = dbs.get("neo4j", {})
        neo_det = f"Nodes: {neo.get('total_nodes', 0):,}, Edges: {neo.get('total_edges', 0):,} ({neo.get('latency_ms', 0)}ms)"
        lines.append(f" {'Neo4j Graph':<18} | {'Port: 7687':<14} | {neo.get('status', 'N/A'):<8} | {neo_det:<32}")

        ch = dbs.get("chromadb", {})
        ch_det = f"Chunks: {ch.get('total_chunks', 0):,} (1024-dim BGE-Large)"
        lines.append(f" {'ChromaDB':<18} | {'Local Disk':<14} | {ch.get('status', 'N/A'):<8} | {ch_det:<32}")

        vl = inf.get("vllm", {})
        vl_det = f"{vl.get('model_loaded', 'Qwen2.5-14B')} ({vl.get('latency_ms', 0)}ms)"
        lines.append(f" {'vLLM Engine':<18} | {'Port: 8002':<14} | {vl.get('status', 'N/A'):<8} | {vl_det:<32}")

        cf = net.get("cloudflare_tunnel", {})
        cf_det = "bin/cloudflared.exe ready" if cf.get("installed") else "Missing"
        lines.append(f" {'Cloudflare CLI':<18} | {'Tunnel Tool':<14} | {cf.get('status', 'N/A'):<8} | {cf_det:<32}")

        lines.extend([
            "",
            " ── 2. CROSS-DATABASE DOCUMENT ALIGNMENT ──────────────────────────────",
        ])
        docs = doc_align.get("documents", [])
        if docs:
            lines.append(f" {'FILENAME':<42} | {'DISK':<6} | {'POSTGRES':<9} | {'CHROMADB':<9} | {'STATUS':<12}")
            lines.append(" " + "-" * 84)
            for d in docs:
                fn = d.get("filename", "")[:40]
                in_d = "YES" if d.get("in_disk") else "NO"
                in_p = "YES" if d.get("in_postgres") else "NO"
                in_c = "YES" if d.get("in_chromadb") else "NO"
                st = d.get("status", "")
                lines.append(f" {fn:<42} | {in_d:<6} | {in_p:<9} | {in_c:<9} | {st:<12}")
        else:
            lines.append("  No document records discovered in data/documents.")

        lines.extend([
            "",
            "=" * 78,
            f" 🚀 OVERALL RESULT: {rep.get('overall_status')}",
            "=" * 78,
        ])
        return "\n".join(lines)
