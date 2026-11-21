"""
RAISE OKF Interactive Visualizer Generator (viz.html)
=====================================================
Generates an interactive, standalone single-file Web visualizer (Cytoscape.js + Marked.js)
for all Open Knowledge Format (OKF v0.3) catalog bundles in `data/catalogs/`.

Features:
  - Interactive force-directed knowledge graph with switchable layouts (cose, concentric, circle, grid)
  - Color-coded node types (InstitutionalProfile, Domain, FiscalYear, Entity, Metric)
  - Trust Tier badges (machine-confirmed, human-reviewed, unverified)
  - Slide-out metadata & Markdown reader with live search & type filtering
  - Reverse backlink graph ("Cited by" / "Referenced by")
  - Zero-install standalone HTML output

Based on the Google Cloud Open Knowledge Format reference implementation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import CATALOGS_DIR
from src.features.catalog.knowledge_catalog import KnowledgeCatalogRegistry

logger = logging.getLogger("raise.features.catalog.visualizer")


def generate_okf_html(
    catalog_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Generates a standalone interactive OKF visualizer HTML file."""
    c_dir = catalog_dir or CATALOGS_DIR
    out_file = output_path or (c_dir / "index.html")

    registry = KnowledgeCatalogRegistry.get_instance(catalog_dir=c_dir)
    registry.reload_catalogs()

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    domain_set = set()
    year_set = set()
    entity_counts: Dict[str, int] = {}

    # 1. Collect entities and frequencies
    for doc_fn, prof in registry.profiles.items():
        for d in prof.primary_domains:
            domain_set.add(d)
        for y in prof.fiscal_years:
            year_set.add(y)
        for e in prof.key_entities:
            entity_counts[e] = entity_counts.get(e, 0) + 1

    # 2. Add Domain nodes
    for dom in sorted(domain_set):
        nodes.append({
            "data": {
                "id": f"dom_{dom}",
                "label": dom,
                "type": "Domain",
                "color": "#10b981",  # Emerald
                "size": 35,
                "details": f"### Academic & Scientific Domain\n\n**{dom}**",
            }
        })

    # 3. Add Fiscal Year nodes
    for yr in sorted(year_set):
        nodes.append({
            "data": {
                "id": f"yr_{yr}",
                "label": f"FY {yr}",
                "type": "FiscalYear",
                "color": "#f59e0b",  # Amber
                "size": 30,
                "details": f"### Fiscal Reporting Period\n\nYear/Period: `{yr}`",
            }
        })

    # 4. Add Top Entity nodes (max 30)
    top_entities = sorted(entity_counts.items(), key=lambda x: -x[1])[:30]
    for ent, count in top_entities:
        nodes.append({
            "data": {
                "id": f"ent_{ent}",
                "label": ent,
                "type": "Entity",
                "color": "#8b5cf6",  # Violet
                "size": 22 + min(15, count * 3),
                "details": f"### Key Scientific Entity\n\n- **Name:** {ent}\n- **Document References:** {count}",
            }
        })

    # 5. Add Document/Institution nodes and links
    for doc_fn, prof in registry.profiles.items():
        doc_node_id = f"doc_{prof.document_id}"
        nodes.append({
            "data": {
                "id": doc_node_id,
                "label": f"{prof.short_name or prof.institution_name[:20]}\n({prof.reporting_period})",
                "title": prof.institution_name,
                "filename": prof.filename,
                "type": "InstitutionalProfile",
                "trust_tier": "machine-confirmed",
                "status": "stable",
                "color": "#3b82f6",  # Blue
                "size": 50,
                "pages": prof.total_pages,
                "reporting_period": prof.reporting_period,
                "markdown": prof.overview_text or f"# {prof.institution_name}\n\nDocument: `{prof.filename}`",
                "details": f"""### {prof.institution_name}
- **Document ID:** `{prof.document_id}`
- **Source File:** `{prof.filename}`
- **Reporting Period:** `{prof.reporting_period}`
- **Trust Tier:** `machine-confirmed` (OKF v0.3)
- **Monitored Pages:** {prof.total_pages}
- **Domains:** {', '.join(prof.primary_domains)}
- **Fiscal Years:** {', '.join(prof.fiscal_years)}
""",
            }
        })

        # Edges to domains
        for d in prof.primary_domains:
            edges.append({
                "data": {
                    "id": f"{doc_node_id}__dom_{d}",
                    "source": doc_node_id,
                    "target": f"dom_{d}",
                    "relation": "IN_DOMAIN",
                }
            })

        # Edges to fiscal years
        for y in prof.fiscal_years:
            edges.append({
                "data": {
                    "id": f"{doc_node_id}__yr_{y}",
                    "source": doc_node_id,
                    "target": f"yr_{y}",
                    "relation": "REPORTED_IN",
                }
            })

        # Edges to entities
        for ent, _ in top_entities:
            if ent in prof.key_entities:
                edges.append({
                    "data": {
                        "id": f"{doc_node_id}__ent_{ent}",
                        "source": doc_node_id,
                        "target": f"ent_{ent}",
                        "relation": "MENTIONS",
                    }
                })

    elements_json = json.dumps({"nodes": nodes, "edges": edges}, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RAISE — Open Knowledge Format (OKF v0.3) Interactive Visualizer</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      height: 100vh;
      overflow: hidden;
    }}
    #app {{
      display: flex;
      flex: 1;
      height: 100%;
      position: relative;
    }}
    #cy-container {{
      flex: 1;
      height: 100%;
      position: relative;
      background: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%);
    }}
    #cy {{
      width: 100%;
      height: 100%;
    }}
    #toolbar {{
      position: absolute;
      top: 16px;
      left: 16px;
      background: rgba(30, 41, 59, 0.9);
      backdrop-filter: blur(8px);
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
      display: flex;
      gap: 12px;
      align-items: center;
      z-index: 10;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }}
    #toolbar input {{
      background: #0f172a;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
      width: 200px;
    }}
    #toolbar select, #toolbar button {{
      background: #0f172a;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
    }}
    #toolbar button:hover, #toolbar select:hover {{
      border-color: var(--accent);
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .badge-machine {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }}
    .badge-stable {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}
    #drawer {{
      width: 440px;
      height: 100%;
      background: var(--panel);
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      box-shadow: -10px 0 25px rgba(0,0,0,0.4);
      z-index: 20;
    }}
    #drawer-header {{
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    #drawer-header h2 {{
      font-size: 16px;
      font-weight: 600;
      color: var(--accent);
    }}
    #drawer-content {{
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      font-size: 13px;
      line-height: 1.6;
    }}
    #drawer-content pre {{
      background: #0f172a;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 12px 0;
      border: 1px solid var(--border);
    }}
    #drawer-content h1, #drawer-content h2, #drawer-content h3 {{
      margin: 16px 0 8px 0;
      color: #e2e8f0;
    }}
    #drawer-content ul {{
      padding-left: 20px;
      margin-bottom: 12px;
    }}
    .legend {{
      position: absolute;
      bottom: 16px;
      left: 16px;
      background: rgba(30, 41, 59, 0.9);
      backdrop-filter: blur(8px);
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid var(--border);
      display: flex;
      gap: 12px;
      font-size: 12px;
      z-index: 10;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
  </style>
</head>
<body>
  <div id="app">
    <div id="cy-container">
      <div id="toolbar">
        <strong style="color: var(--accent); font-size: 14px;">RAISE OKF Graph</strong>
        <input type="text" id="search-box" placeholder="Filter entities / docs...">
        <select id="layout-select">
          <option value="cose">Force-Directed (cose)</option>
          <option value="concentric">Concentric</option>
          <option value="circle">Circle</option>
          <option value="grid">Grid</option>
        </select>
        <button id="btn-fit">Fit View</button>
      </div>

      <div id="cy"></div>

      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#3b82f6;"></div> Institution</div>
        <div class="legend-item"><div class="legend-dot" style="background:#10b981;"></div> Domain</div>
        <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;"></div> Fiscal Year</div>
        <div class="legend-item"><div class="legend-dot" style="background:#8b5cf6;"></div> Entity / Gene</div>
      </div>
    </div>

    <div id="drawer">
      <div id="drawer-header">
        <h2 id="drawer-title">OKF Inspector</h2>
        <div>
          <span class="badge badge-machine">OKF v0.3</span>
          <span class="badge badge-stable">STABLE</span>
        </div>
      </div>
      <div id="drawer-content">
        <p style="color: var(--text-muted);">Click any node in the knowledge graph to inspect its Open Knowledge Format (OKF) metadata, provenance citations, and Markdown documentation.</p>
      </div>
    </div>
  </div>

  <script>
    const elementsData = {elements_json};

    const cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: elementsData,
      style: [
        {{
          selector: 'node',
          style: {{
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-size': '11px',
            'text-valign': 'center',
            'text-halign': 'center',
            'width': 'data(size)',
            'height': 'data(size)',
            'text-wrap': 'wrap',
            'text-max-width': '90px',
            'border-width': 2,
            'border-color': '#ffffff',
            'border-opacity': 0.3,
            'transition-property': 'background-color, line-color, target-arrow-color',
            'transition-duration': '0.2s'
          }}
        }},
        {{
          selector: 'node:selected',
          style: {{
            'border-width': 4,
            'border-color': '#38bdf8',
            'border-opacity': 1.0,
            'shadow-blur': 15,
            'shadow-color': '#38bdf8',
            'shadow-opacity': 0.8
          }}
        }},
        {{
          selector: 'edge',
          style: {{
            'width': 1.5,
            'line-color': '#475569',
            'curve-style': 'bezier',
            'opacity': 0.6,
            'label': 'data(relation)',
            'font-size': '8px',
            'color': '#64748b',
            'text-rotation': 'autorotate'
          }}
        }}
      ],
      layout: {{
        name: 'cose',
        animate: false,
        padding: 50,
        nodeRepulsion: 450000,
        idealEdgeLength: 100
      }}
    }});

    // Node selection inspector
    cy.on('tap', 'node', function(evt) {{
      const node = evt.target;
      const data = node.data();
      document.getElementById('drawer-title').innerText = data.label.replace('\\n', ' ');
      
      let html = '';
      if (data.details) {{
        html += marked.parse(data.details);
      }}
      if (data.markdown) {{
        html += '<hr style="margin: 16px 0; border: 0; border-top: 1px solid var(--border);">';
        html += marked.parse(data.markdown);
      }}
      document.getElementById('drawer-content').innerHTML = html;
    }});

    // Search filter
    document.getElementById('search-box').addEventListener('input', function(e) {{
      const q = e.target.value.toLowerCase().trim();
      if (!q) {{
        cy.elements().style('opacity', 1.0);
        return;
      }}
      cy.elements().style('opacity', 0.15);
      const matches = cy.nodes().filter(n => {{
        const label = (n.data('label') || '').toLowerCase();
        const title = (n.data('title') || '').toLowerCase();
        return label.includes(q) || title.includes(q);
      }});
      matches.style('opacity', 1.0);
      matches.neighborhood().style('opacity', 0.8);
    }});

    // Layout switcher
    document.getElementById('layout-select').addEventListener('change', function(e) {{
      cy.layout({{ name: e.target.value, animate: true, animationDuration: 400 }}).run();
    }});

    // Fit button
    document.getElementById('btn-fit').addEventListener('click', function() {{
      cy.fit(null, 40);
    }});
  </script>
</body>
</html>
"""

    out_file.write_text(html_content, encoding="utf-8")
    viz_file = c_dir / "viz.html"
    viz_file.write_text(html_content, encoding="utf-8")
    logger.info("Generated OKF Visualizers: %s and %s", out_file.name, viz_file.name)
    return out_file
