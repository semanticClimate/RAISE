# RETRIEVAL QA CHAT PROMPT (CYPHER QUERY GENERATION)

```markdown
Task: Translate the user's natural language question into a syntactically correct, schema-compliant Cypher query to retrieve information from a Graph Database built from institutional annual reports.

==================================================
GRAPH SCHEMA DEFINITION
==================================================

1. NODE LABELS & PROPERTIES:

   - Institution:
       • name: String (e.g., "Indian Institute of Science", "National Research Council")
       • type: String (e.g., "University", "Research Institute", "Research Council", "Foundation")
       • location: String

   - AnnualReport:
       • fiscal_year: String (e.g., "2024-25", "2023-24", "2025")
       • title: String

   - Section:
       • parent_institution: String
       • type: String (Allowed values:
           "Executive Summary",
           "Financial Statements & Budgets",
           "Sponsored Research Projects & Grants",
           "Patents & Intellectual Property",
           "Startups & Incubation",
           "Academic Programs & Degrees",
           "Governance & Strategic Initiatives",
           "Global Partnerships & MoUs",
           "Endowments & Investments",
           "Facilities & Infrastructure",
           "Audit & Compliance Reports")

   - Chunk:
       • chunk_id: String
       • text: String
       • page_number: Integer

   - Table:
       • table_id: String
       • caption: String
       • headers: List of Strings

   - Department:
       • name: String (e.g., "Department of Computer Science", "Department of Biotechnology")

   - CentreOfExcellence:
       • name: String (e.g., "Centre for Clean Energy", "Advanced Computing Hub")

   - BoardOfGovernors:
       • name: String

   - ExecutiveRole:
       • title: String (e.g., "Director", "Vice-Chancellor", "Dean", "Registrar", "Treasurer")

   - Person:
       • name: String (full name without honorific prefix)
       • designation: String (e.g., "Professor", "Scientist", "Principal Investigator", "Director")

   - Award:
       • title: String
       • year: String

   - SponsorAgency:
       • name: String (e.g., "DST", "DBT", "CSIR", "MeitY", "Gates Foundation")
       • type: String (e.g., "Government", "Industry", "Foundation")

   - Grant:
       • title: String
       • grant_id: String
       • sponsor_agency: String
       • amount_inr_lakh: Float

   - Equipment:
       • name: String (e.g., "Cryo-EM", "Confocal Microscope", "HPC Cluster")
       • cost: Float

   - Patent:
       • title: String
       • patent_id: String
       • status: String (Allowed values: "Filed", "Granted")
       • filing_year: String

   - Technology:
       • name: String

   - IndustryPartner:
       • name: String

   - FinancialStream:
       • type: String
       • amount: Float

   - Incubator:
       • name: String (e.g., "Technology Business Incubator", "Bio-Incubator")

   - Startup:
       • name: String
       • valuation: String
       • sector: String (e.g., "Deep-Tech", "Healthcare", "Clean Energy", "Biotechnology")

   - Investor:
       • name: String

   - Milestone:
       • description: String (e.g., "Regulatory Approval", "Commercial Launch", "Patent Licensing")

   - AcademicProgram:
       • name: String (e.g., "B.Tech in Artificial Intelligence", "PhD in Computational Biology")
       • degree_level: String (e.g., "UG", "PG", "PhD", "Dual Degree")

   - ForeignUniversity:
       • name: String
       • country: String

   - Student:
       • student_id: String

   - Fellowship:
       • name: String (e.g., "Prime Minister's Research Fellowship", "Post-Doctoral Fellowship")

   - MoU:
       • title: String
       • date_signed: String

   - ResearchArea:
       • name: String (e.g., "Genomics", "Quantum Computing", "Clean Energy", "Robotics")

   - CorporateEntity:
       • name: String

   - EndowmentFund:
       • name: String
       • corpus_value: Float

   - FinancialStatement:
       • type: String (Allowed values: "Balance Sheet", "Income & Expenditure", "Cash Flow")
       • fiscal_year: String

   - RevenueStream:
       • source: String (e.g., "Sponsored Research", "Consultancy", "Tuition", "Government Grants")
       • amount: Float

   - ExpenseCategory:
       • category: String (e.g., "Salaries", "Equipment Maintenance", "Research & Development")
       • amount: Float

   - Scholarship:
       • name: String

   - AuditFirm:
       • name: String

   - Facility:
       • name: String

2. DIRECTED RELATIONSHIP TYPES & DESCRIPTIONS:

   [1. Document Hierarchy & Chunking]
   • (:Institution)-[:PUBLISHED]->(:AnnualReport) — Links an institution to its annual report.
   • (:AnnualReport)-[:HAS_SECTION]->(:Section) — Connects a report to its primary thematic sections.
   • (:Section)-[:HAS_SUBSECTION]->(:Section) — Captures nested sub-sections within chapters.
   • (:Section)-[:HAS_CHUNK]->(:Chunk) — Connects a section to indexed text chunks.
   • (:Chunk)-[:CONTAINS_TABLE]->(:Table) — Connects a text chunk to extracted tabular data.
   • (:Section)-[:MENTIONS]->(:Patent | :Startup | :Grant | :Person | :Facility) — Direct entity mentions in a section.

   [2. Governance & Organizational Structure]
   • (:Institution)-[:HAS_DEPARTMENT]->(:Department) — Links an institution to academic departments or schools.
   • (:Institution)-[:OPERATES_CENTRE]->(:CentreOfExcellence) — Links an institution to interdisciplinary research centres.
   • (:Institution)-[:GOVERNED_BY]->(:BoardOfGovernors) — Links an institution to its governing board or senate.
   • (:Person)-[:SERVES_ON]->(:BoardOfGovernors) — Connects members, nominees, or trustees to governing boards.
   • (:Person)-[:HOLDS_ROLE]->(:ExecutiveRole) — Associates personnel with leadership positions.

   [3. Faculty, Researchers & Human Capital]
   • (:Institution)-[:EMPLOYEES_FACULTY]->(:Person) — Links faculty and scientists to their institution.
   • (:Department)-[:AFFILIATED_WITH]->(:Person) — Maps researchers to their primary or joint department.
   • (:Person)-[:SUPERVISES]->(:Person) — Captures supervision between PIs and PhD scholars/postdocs.
   • (:Person)-[:AWARDED_HONOR]->(:Award) — Links personnel to academic, national, or international awards.

   [4. Research Grants & Sponsored Projects]
   • (:Institution)-[:SECURED_GRANT]->(:Grant) — Links an institution to externally funded projects.
   • (:SponsorAgency)-[:FUNDED_GRANT]->(:Grant) — Connects funding agencies to sponsored grants.
   • (:Person)-[:PRINCIPAL_INVESTIGATOR]->(:Grant) — Identifies the lead investigator of a grant.
   • (:Person)-[:CO_INVESTIGATOR]->(:Grant) — Connects co-PIs to a grant.
   • (:Department)-[:HOSTS_PROJECT]->(:Grant) — Maps a grant to its host department.
   • (:Grant)-[:FUNDED_EQUIPMENT]->(:Equipment) — Connects grants to procured instruments.

   [5. Patents, Intellectual Property & Tech Transfer]
   • (:Institution)-[:FILED_PATENT]->(:Patent) — Connects an institution to filed patent applications.
   • (:Institution)-[:GRANTED_PATENT]->(:Patent) — Connects an institution to granted patents.
   • (:Person)-[:INVENTED]->(:Patent) — Connects inventors to a patent.
   • (:Institution)-[:LICENSED_TECHNOLOGY]->(:Technology) — Links an institution to licensed technologies.
   • (:Technology)-[:LICENSED_TO]->(:IndustryPartner) — Connects technologies to commercial licensees.
   • (:Institution)-[:EARNED_ROYALTY]->(:FinancialStream) — Links licensing to royalty revenue streams.

   [6. Entrepreneurship, Incubation & Spin-off Startups]
   • (:Institution)-[:OPERATES_INCUBATOR]->(:Incubator) — Links an institution to its incubator or research park.
   • (:Incubator)-[:INCUBATED]->(:Startup) — Connects an incubator to incubated startups.
   • (:Person)-[:FOUNDED]->(:Startup) — Connects faculty, student, or alumni founders to startups.
   • (:Startup)-[:ORIGINATED_FROM]->(:Technology) — Links a startup to institutional IP/technology.
   • (:Investor)-[:INVESTED_IN]->(:Startup) — Captures seed, angel, or VC investments in startups.
   • (:Startup)-[:ACHIEVED_MILESTONE]->(:Milestone) — Tracks key startup milestones.

   [7. Academic Programs, Degrees & Fellowships]
   • (:Institution)-[:OFFERS_PROGRAM]->(:AcademicProgram) — Links an institution to degree programs.
   • (:Department)-[:ADMINISTERS_DEGREE]->(:AcademicProgram) — Maps degree offerings to managing departments.
   • (:AcademicProgram)-[:PARTNERED_WITH]->(:ForeignUniversity) — Links joint/dual degrees to partner foreign universities.
   • (:Student)-[:ENROLLED_IN]->(:AcademicProgram) — Connects students to degree programs.
   • (:Person)-[:AWARDED_FELLOWSHIP]->(:Fellowship) — Links researchers or students to fellowships.

   [8. Global Alliances, Partnerships & MoUs]
   • (:Institution)-[:COLLABORATED_WITH]->(:Institution) — Captures inter-institutional partnerships.
   • (:Institution)-[:ENTERED_MOU]->(:MoU) — Connects institutions to signed MoUs.
   • (:MoU)-[:FOCUSES_ON]->(:ResearchArea) — Connects MoUs to target research areas.
   • (:Institution)-[:PARTNERED_INDUSTRY]->(:CorporateEntity) — Links institutions to corporate R&D/CSR partners.

   [9. Financial Statements, Endowments & Budgets]
   • (:Institution)-[:MANAGES_ENDOWMENT]->(:EndowmentFund) — Connects an institution to endowment funds.
   • (:AnnualReport)-[:CONTAINS_FINANCIAL_STATEMENT]->(:FinancialStatement) — Links a report to financial statements.
   • (:FinancialStatement)-[:REPORTS_REVENUE]->(:RevenueStream) — Maps reported income streams.
   • (:FinancialStatement)-[:REPORTS_EXPENSE]->(:ExpenseCategory) — Maps reported expenditure categories.
   • (:EndowmentFund)-[:ALLOCATED_TO]->(:Scholarship) — Connects endowments to funded scholarships/chairs.
   • (:AuditFirm)-[:AUDITED]->(:FinancialStatement) — Links external auditors to financial statements.

   [10. Facilities, Infrastructure & Shared Resources]
   • (:Institution)-[:HOUSES_EQUIPMENT]->(:Equipment) — Connects an institution to major research instruments.
   • (:Department)-[:UTILIZES_FACILITY]->(:Facility) — Links departments to central facilities.

==================================================
INSTRUCTIONS & COMPLIANCE RULES
==================================================

1. STRICT SCHEMA GROUNDING & ANTI-HALLUCINATION:
   - Use ONLY the node labels, relationship types, and property keys explicitly defined in the schema above.
   - NEVER introduce, infer, or hallucinate unlisted node labels, relationship types, or property keys.
   - If the user's question asks for a concept not represented as a dedicated node label, fall back to matching `Section` or `Chunk` nodes containing relevant text terms.

2. READ-ONLY SECURITY CONSTRAINTS:
   - Generate STRICTLY READ-ONLY Cypher queries using `MATCH`, `OPTIONAL MATCH`, `WITH`, `WHERE`, `UNWIND`, `RETURN`, `ORDER BY`, and `LIMIT`.
   - ABSOLUTELY FORBIDDEN: Any mutating or administrative clauses (`CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`, `DETACH`, `DROP`, `CALL dbms.*`, `CALL apoc.*`).

3. DOCUMENT HIERARCHY & SECTION-BASED SCOPING:
   - When extracting text chunks, traverse through `Section` nodes (`(:AnnualReport)-[:HAS_SECTION]->(sec:Section)-[:HAS_CHUNK]->(chk:Chunk)`).
   - Filter `sec.type` when the query domain clearly maps to one of the 11 allowed `Section.type` values. If the target section is ambiguous, do not restrict `sec.type`.

4. CASE-INSENSITIVE & ACRONYM-AWARE ENTITY MATCHING:
   - Strip leading titles/honorifics (`Dr.`, `Prof.`, `Mr.`, `Ms.`, `Shri`) when matching `Person.name`.
   - When matching institution or agency names that may appear as either an acronym or full name, match against both forms using case-insensitive `CONTAINS` or `OR`:
     `WHERE toLower(inst.name) CONTAINS toLower($inst_short) OR toLower(inst.name) CONTAINS toLower($inst_full)`
   - Always use case-insensitive partial matching (`toLower(n.name) CONTAINS toLower(...)`) rather than exact equality (`=`) on free-text string properties.

5. CYPHER SYNTAX, TRAVERSAL & PERFORMANCE GUARDRAILS:
   - Respect exact relationship arrow directions as defined in Section 2.
   - Always use `DISTINCT` in `RETURN` clauses and aggregations (`count(DISTINCT n)`, `collect(DISTINCT n)`) to prevent duplicate path rows.
   - Never use unbounded variable-length paths (`-[*]-`). Bound any variable-length path strictly (e.g., `-[:HAS_SUBSECTION*1..3]->`).
   - Use `OPTIONAL MATCH` for secondary attributes so primary matches are not dropped when optional links are absent.

6. AGGREGATION, TYPE CASTING & NULL SAFETY:
   - Cast numeric properties explicitly with `toFloat()` or `toInteger()` when aggregating (`SUM`, `AVG`, `MIN`, `MAX`), and guard against nulls using `coalesce(val, 0)`.

7. OUTPUT FORMATTING & ZERO-COMMENTARY RULE:
   - Output ONLY the raw executable Cypher query without markdown backticks, commentary, or explanations.
```
