import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.graph.engine import GraphRAGEngine

def test_graph_detection():
    engine = GraphRAGEngine()

    # Sample chunks representing an institutional report
    sample_chunks = [
        {
            "chunk_id": "chk_1",
            "heading": "Department of Computer Science & Quantum Labs",
            "source_pages": [4],
            "plain_text": "Dr. Karthik Raman at Indian Institute of Technology Madras received Rs. 45.5 Crore in funding from DBT for research on algorithms."
        },
        {
            "chunk_id": "chk_2",
            "heading": "Startups and Deep-Tech Incubation",
            "source_pages": [12],
            "plain_text": "IIT Madras Research Park and Bioincubator incubated Ather Energy and Mindgrove under the guidance of Prof. John Doe."
        },
        {
            "chunk_id": "chk_3",
            "heading": "Biotechnology & Health Sciences",
            "source_pages": [25],
            "plain_text": "BRIC and NIPGR collaborated on plant genomics with Director Sushanta Kumar Panigrahi securing Rs. 12.8 Crore grant."
        }
    ]

    gdata = engine.build_from_chunks(sample_chunks, doc_id="IITM_Annual_Report")
    print(f"=== GRAPH BUILT: {gdata['node_count']} nodes, {gdata['edge_count']} edges ===\n")

    # 1. Detect Communities
    communities = engine.detect_communities()
    print("=== DETECTED COMMUNITIES ===")
    for comm in communities:
        print(f"Community #{comm['community_id']}: Domain={comm['primary_domain']}, Size={comm['size']}, Top Hubs={comm['top_hubs']}")

    # 2. Centrality Metrics
    metrics = engine.compute_centrality_metrics()
    print("\n=== TOP 5 CENTRAL NODES (BY PAGERANK) ===")
    sorted_nodes = sorted(metrics.items(), key=lambda x: x[1]['pagerank'], reverse=True)[:5]
    for nid, m in sorted_nodes:
        print(f"- Node: {nid:45} | PageRank: {m['pagerank']:.4f} | Degree: {m['degree_centrality']:.4f}")

    # 3. Hierarchical Summaries
    summaries = engine.generate_hierarchical_summaries()
    print("\n=== HIERARCHICAL SUMMARIES ===")
    for s in summaries:
        print(f"* {s['summary']}")

    assert gdata["node_count"] > 0
    assert gdata["edge_count"] > 0
    assert len(communities) > 0
    assert len(metrics) > 0
    assert len(summaries) > 0

if __name__ == "__main__":
    test_graph_detection()
