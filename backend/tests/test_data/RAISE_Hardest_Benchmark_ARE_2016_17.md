# RAISE Hardest Benchmark — IIT (ISM) Dhanbad Annual Report 2016–17

**Source document:** `ARE-2016-17.pdf`  
**Institution:** Indian Institute of Technology (Indian School of Mines), Dhanbad  
**Report:** Annual Report 2016–2017  
**Document length:** 442 PDF pages

This benchmark is designed to stress-test the RAISE hybrid GraphRAG pipeline described in the project architecture. It intentionally mixes:

- exact entity/name retrieval;
- entity → project → department → sponsor relationships;
- multi-section and multi-hop joins;
- table arithmetic and unit conversion;
- percentage verification against values reported by the document;
- chronology and role changes;
- contradiction/inconsistency detection;
- negative/unanswerable questions;
- questions where a plausible answer requires an unsupported inference.

## Evaluation contract

For every question, RAISE should:

1. Answer only from the active source document.
2. Cite the exact supporting page(s)/section(s).
3. Preserve names, titles, project numbers, sponsor names and wording closely enough to be auditable.
4. Show intermediate arithmetic for calculation questions.
5. Distinguish **reported percentages** from **recomputed percentages**.
6. Never silently repair an inconsistency in the report.
7. Return `unable_to_verify` when the requested fact cannot be established from the source.
8. Never infer a missing entity merely because the surrounding evidence makes one seem likely.

### Severity scale

- **HARD:** requires precise retrieval plus one non-trivial operation.
- **VERY HARD:** requires multiple evidence locations or multi-hop joins.
- **EXTREME:** requires multi-hop joins + arithmetic + ambiguity/contradiction handling.
- **ADVERSARIAL:** designed to catch hallucination, silent reconciliation, scope leakage, or overconfident inference.

---

# Benchmark Questions

## A. Institutional identity, chronology and structure

### Q01 — IIT conversion chronology
**Severity:** HARD  
**Category:** chronology + exact entity

**Question:**  
According to the report, in what year was the institution established, what statutory status did it obtain in 1967, and on what exact date in 2016 was it conferred IIT status? Give the institution's resulting name exactly as stated.

**Gold answer:**  
Established in **1926** as Indian School of Mines, Dhanbad; it became a **Deemed to be University under Section 3 of the UGC Act, 1956 in 1967**; it was conferred IIT status on **6 September 2016** and renamed **Indian Institute of Technology (Indian School of Mines), Dhanbad**.

**Expected evidence:**  
Section 1, *About IIT (ISM), Dhanbad*, printed pp. 1–3 (PDF pp. 31–33).

**Expected quality gate:** `accept`

**Trap:**  
Do not substitute a generic IIT history or use a modern institutional name that is not the report's exact wording.

---

### Q02 — Oldest and newest departments
**Severity:** HARD  
**Category:** entity relationship + chronology

**Question:**  
Among the 18 departments listed by the report, identify the earliest-established department(s) and the latest-established department, including their establishment years. Do not infer an earlier/later department from general institutional history; use the department table.

**Gold answer:**  
Earliest: **Department of Applied Geology (1926), Department of Mining Engineering (1926), Department of Humanities and Social Sciences (1926)**.  
Latest: **Department of Civil Engineering (2013)**.

**Expected evidence:**  
Section 1 department table, printed pp. 2–3 (PDF pp. 32–33).

**Expected quality gate:** `accept`

**Trap:**  
The fact that the institute began with Mining Engineering and Applied Geology does not mean Humanities and Social Sciences was established later; the table explicitly gives all three as 1926.

---

### Q03 — Programme expansion
**Severity:** VERY HARD  
**Category:** calculation + list retrieval

**Question:**  
The report says IIT (ISM) offered 48 UG/PG programmes in 2010–11 and 65 in 2016–17. Calculate the exact percentage increase from 48 to 65, then name the four new undergraduate/dual-degree programmes explicitly identified as added during the six-year period.

**Gold answer:**  
Increase = `((65 - 48) / 48) × 100 = 35.4167%` ≈ **35.42%**.

The four identified programmes are:
1. **B.Tech (Civil Engineering)**
2. **B.Tech (Electronics & Instrumentation Engineering)**
3. **B.Tech (Engineering Physics)**
4. **Dual Degree (Computer Science & Engineering)**

**Expected evidence:**  
Executive Summary, printed pp. v–vi (PDF pp. 9–10).

**Expected quality gate:** `accept`

**Trap:**  
Do not count every listed M.Tech programme as one of these four undergraduate additions.

---

# B. Student tables and numerical consistency

### Q04 — Total B.Tech population and gender fraction
**Severity:** HARD  
**Category:** table arithmetic

**Question:**  
Using the 2016–17 B.Tech table, what is the total student strength, how many are female, and what percentage of the total is female? Give the computed percentage to two decimal places.

**Gold answer:**  
Total = **3,247**; female = **177**.  
Female proportion = `177 / 3247 × 100` = **5.45%**.

**Expected evidence:**  
Section 2.1, *Undergraduate Programmes*, printed p. 6 (PDF p. 36).

**Expected quality gate:** `accept`

---

### Q05 — B.Tech programme extremes
**Severity:** HARD  
**Category:** ranking + exact table retrieval

**Question:**  
Among the 13 B.Tech disciplines in 2016–17, which has the largest total student strength and which has the smallest non-zero total? Give both discipline names and totals.

**Gold answer:**  
Largest: **Computer Science & Engineering — 526**.  
Smallest non-zero: **Engineering Physics — 40**.

**Expected evidence:**  
Printed p. 6 (PDF p. 36).

**Expected quality gate:** `accept`

---

### Q06 — Dual-degree discontinuation trap
**Severity:** VERY HARD  
**Category:** status + table interpretation

**Question:**  
In the 5-year Dual Degree table, five programmes are marked “Discontinued” while one is not. Identify the non-discontinued programme, its sanctioned strength, semester-wise totals and overall total.

**Gold answer:**  
**5yr. Dual Degree Computer Science & Engg. + Computer Science & Engg.**  
Sanctioned strength = **18**.  
Semester totals: **I = 18, III = 19, V = 24, VII = 17, IX = –**.  
Overall total = **78**.

**Expected evidence:**  
Section 2.2, printed p. 7 (PDF p. 37).

**Expected quality gate:** `accept`

**Trap:**  
Do not treat “Discontinued” as zero enrollment; the report still lists historical cohorts in those rows.

---

### Q07 — M.Tech highest-enrolment branch
**Severity:** HARD  
**Category:** ranking + table

**Question:**  
Among the 27 two-year M.Tech programmes listed, which has the highest total student strength? Give the top three and the difference between first and second.

**Gold answer:**  
1. **Electronics & Communication Engineering — 130**  
2. **Computer Science & Engineering — 98**  
3. **Computer Science & Engineering (Specialization in Information Security) — 96**

Difference between first and second = **32 students**.

**Expected evidence:**  
Section 2.4, printed p. 9 (PDF p. 39).

**Expected quality gate:** `accept`

---

### Q08 — Gender comparison across two academic levels
**Severity:** EXTREME  
**Category:** cross-table calculation

**Question:**  
Compare the female-student proportion in 4-year B.Tech and 2-year M.Tech. Compute both percentages and state how many times larger the M.Tech female proportion is than the B.Tech female proportion.

**Gold answer:**  
B.Tech: `177 / 3247 × 100` = **5.45%**.  
2-year M.Tech: `282 / 1357 × 100` = **20.78%**.  
Ratio = `20.78 / 5.45` ≈ **3.81×**.

**Expected evidence:**  
Printed pp. 6 and 9 (PDF pp. 36 and 39).

**Expected quality gate:** `accept`

**Trap:**  
Do not compare raw female counts (177 vs 282) and call that a proportion.

---

### Q09 — MBA vs Ex-MBA female participation
**Severity:** HARD  
**Category:** table arithmetic

**Question:**  
What are the female counts and female percentages for the 2-year MBA and 3-year Ex-MBA cohorts, and how many percentage points lower is the Ex-MBA female proportion?

**Gold answer:**  
2-year MBA: 24 female / 83 total = **28.92%**.  
3-year Ex-MBA: 2 female / 60 total = **3.33%**.  
Difference = **25.59 percentage points**.

**Expected evidence:**  
Printed p. 8 (PDF p. 38).

**Expected quality gate:** `accept`

---

### Q10 — Attempted reconciliation of total student strength
**Severity:** EXTREME  
**Category:** unanswerability + reconciliation

**Question:**  
The report states total student strength of 7,903 and separately gives the following cohort totals: B.Tech 3,247; Dual Degree 244; Integrated M.Tech 282; M.Sc/M.Sc.Tech 552; MBA 83; Ex-MBA 60; 2-year M.Tech 1,357; IIIF 3-year M.Tech 117. Add these cohorts and compare with 7,903. Can you prove from the report alone exactly which additional 1,961 students make up the difference?

**Gold answer:**  
The listed cohorts sum to **5,942**, leaving **1,961** relative to the headline 7,903. The report excerpted in these tables does **not provide enough evidence to uniquely identify all 1,961 missing students**. RAISE must not invent a category or equate the difference directly with research scholars, because the research-scholar count is **1,894**, not 1,961, and the definitions/totals are not presented as a single reconciliation statement.

**Expected evidence:**  
Executive Summary, printed p. vii (PDF p. 11); academic tables, printed pp. 6–10 (PDF pp. 36–40).

**Expected quality gate:** `unable_to_verify`

**Trap:**  
“1,961 ≈ 1,894 + 67” is arithmetic, not proof of a documented category structure.

---

# C. Research-output growth and adversarial arithmetic

### Q11 — SCOPUS growth verification
**Severity:** EXTREME  
**Category:** calculation + contradiction detection

**Question:**  
The SCOPUS table gives 156 publications in 2010 and 1,237 in 2016 and reports an overall growth of 688%. Recompute the growth directly from the endpoints. Does the source's reported overall-growth percentage exactly match the endpoint calculation?

**Gold answer:**  
Endpoint growth = `((1237 - 156) / 156) × 100` = **692.95%**.  
The table reports **688%**, so the two figures **do not exactly match**.

**Expected evidence:**  
Section 3.1.1, printed p. 10 (PDF p. 14).

**Expected quality gate:** `accept`

**Trap:**  
Do not silently replace 688% with 692.95%; preserve both and explain the discrepancy.

---

### Q12 — Web of Science growth verification
**Severity:** EXTREME  
**Category:** calculation + contradiction detection

**Question:**  
The Web of Science table gives 113 publications in 2010 and 1,057 in 2016 and reports 836% overall growth. Recompute the endpoint growth and state whether the discrepancy is materially different from the SCOPUS case.

**Gold answer:**  
Endpoint growth = `((1057 - 113) / 113) × 100` = **835.40%**.  
Reported overall growth = **836%**, which is consistent after rounding.  
Unlike the SCOPUS table, this is not a large reporting discrepancy.

**Expected evidence:**  
Section 3.1.2, printed p. 11 (PDF p. 15).

**Expected quality gate:** `accept`

---

### Q13 — Research scholar growth
**Severity:** HARD  
**Category:** calculation

**Question:**  
Research scholars increased from 225 in 2010–11 to 1,894 in 2016–17. Compute the endpoint percentage growth and compare it with the report's stated 742%.

**Gold answer:**  
`((1894 - 225) / 225) × 100` = **741.78%**, which rounds to **742%**.

**Expected evidence:**  
Printed p. 11 (PDF p. 15).

**Expected quality gate:** `accept`

---

### Q14 — Ph.D. growth
**Severity:** HARD  
**Category:** table + percentage

**Question:**  
Ph.D. awards rose from 22 in 2010–11 to 167 in 2016–17. Verify the report's 659% overall growth using the endpoint calculation.

**Gold answer:**  
`((167 - 22) / 22) × 100` = **659.09%**, consistent with the reported **659%**.

**Expected evidence:**  
Printed p. 13 (PDF p. 17) and the Ph.D. comparison table.

**Expected quality gate:** `accept`

---

### Q15 — Sponsored project outlay growth
**Severity:** EXTREME  
**Category:** calculation + unit awareness

**Question:**  
The project outlay rose from Rs. 21.98 crore in 2010–11 to Rs. 124.34 crore in 2016–17. Compute the endpoint growth and compare it with the report's cumulative 466%.

**Gold answer:**  
`((124.34 - 21.98) / 21.98) × 100` = **465.70%**, which rounds to **466%**.

**Expected evidence:**  
Section 3.3, printed p. 13 (PDF p. 17).

**Expected quality gate:** `accept`

---

### Q16 — External cash-flow growth
**Severity:** EXTREME  
**Category:** calculation

**Question:**  
External cash flow increased from Rs. 24.43 crore in 2010–11 to Rs. 113.07 crore in 2016–17. Recalculate the cumulative growth and test the reported 363%.

**Gold answer:**  
`((113.07 - 24.43) / 24.43) × 100` = **362.83%**, consistent with **363%** after rounding.

**Expected evidence:**  
Executive Summary / External Cash Flow graph, printed p. xviii (PDF p. 22).

**Expected quality gate:** `accept`

---

### Q17 — Student-strength growth verification
**Severity:** HARD  
**Category:** calculation

**Question:**  
Verify the report's claim that student strength grew by 135% from 3,362 in 2010–11 to 7,903 in 2016–17.

**Gold answer:**  
`((7903 - 3362) / 3362) × 100` = **135.07%**, which rounds to **135%**.

**Expected evidence:**  
Executive Summary, printed p. vii (PDF p. 11).

**Expected quality gate:** `accept`

---

### Q18 — Faculty-strength growth
**Severity:** HARD  
**Category:** calculation

**Question:**  
Full-time faculty increased from 184 in 2010–11 to 284 in 2016–17. What is the exact endpoint percentage increase?

**Gold answer:**  
`((284 - 184) / 184) × 100` = **54.35%**.

**Expected evidence:**  
Executive Summary, printed p. vii (PDF p. 11).

**Expected quality gate:** `accept`

---

### Q19 — International-student growth
**Severity:** HARD  
**Category:** calculation + large percentage

**Question:**  
International students increased from 5 in 2010–11 to 83 in 2016–17. Calculate the percentage growth and absolute increase.

**Gold answer:**  
Absolute increase = **78 students**.  
Percentage growth = `((83 - 5) / 5) × 100` = **1,560%**.

**Expected evidence:**  
Section 7.4, printed p. xxi (PDF p. 25).

**Expected quality gate:** `accept`

**Trap:**  
Do not call 83 “1,660% growth”; 1,660% is the final value expressed as a percentage of the baseline.

---

# D. Financial and quantitative stress tests

### Q20 — Grant-in-aid five-year comparison
**Severity:** EXTREME  
**Category:** image/table arithmetic

**Question:**  
From the Grant-in-Aid chart, calculate the combined Plan + Non-Plan amount for 2012–13 and 2016–17, then calculate the absolute and percentage change in the combined amount.

**Gold answer:**  
2012–13 = **13,500 + 5,395 = 18,895 lakh**.  
2016–17 = **10,000 + 8,520 = 18,520 lakh**.  
Absolute change = **−375 lakh**.  
Percentage change = `375 / 18895 × 100` = **−1.98%** approximately.

**Expected evidence:**  
Annual Accounts Executive Summary, PDF p. 339 (printed financial-account page 309).

**Expected quality gate:** `accept`

---

### Q21 — Internal-income increase
**Severity:** HARD  
**Category:** calculation

**Question:**  
Internal income rose from Rs. 4,690.11 lakh in 2015–16 to Rs. 5,180.25 lakh in 2016–17. Give the absolute increase and percentage increase.

**Gold answer:**  
Absolute increase = **Rs. 490.14 lakh**.  
Percentage increase = `490.14 / 4690.11 × 100` = **10.45%**.

**Expected evidence:**  
Annual Accounts Executive Summary, PDF p. 339.

**Expected quality gate:** `accept`

---

### Q22 — Plan grant allocation
**Severity:** EXTREME  
**Category:** table/chart cross-check

**Question:**  
The institute received Rs. 10,000 lakh of Plan Grant in 2016–17 and incurred Rs. 7,885.86 lakh on creation of capital assets. Calculate the percentage of the Plan Grant represented by this capital-asset expenditure and the residual amount.

**Gold answer:**  
Capital-asset share = `7885.86 / 10000 × 100` = **78.86%**.  
Residual = **Rs. 2,114.14 lakh**.

**Expected evidence:**  
Plan Account, Annual Accounts, PDF p. 340 (printed financial-account page 310).

**Expected quality gate:** `accept`

---

### Q23 — CPWD advance reconciliation
**Severity:** HARD  
**Category:** exact arithmetic consistency

**Question:**  
The Plan Account says Rs. 7,885.86 lakh was incurred for capital assets, of which Rs. 5,555.21 lakh was deposited with CPWD and Rs. 2,330.65 lakh was used for procurement of capital items. Does the decomposition reconcile exactly?

**Gold answer:**  
Yes. `5,555.21 + 2,330.65 = 7,885.86 lakh` exactly at the reported precision.

**Expected evidence:**  
Plan Account, PDF p. 340.

**Expected quality gate:** `accept`

---

### Q24 — Consultancy versus sponsored project outlay
**Severity:** EXTREME  
**Category:** unit conversion + cross-section calculation

**Question:**  
Consultancy projects in FY 2016–17 are reported at Rs. 1,702.30 lakh, while sponsored R&D/industry project outlay is Rs. 124.34 crore. Convert the consultancy amount to crore and calculate consultancy value as a percentage of project outlay.

**Gold answer:**  
Rs. 1,702.30 lakh = **Rs. 17.023 crore**.  
Percentage = `17.023 / 124.34 × 100` = **13.69%** approximately.

**Expected evidence:**  
Consultancy section, printed p. 199 (PDF p. 229); sponsored-project section, printed p. 13 (PDF p. 17).

**Expected quality gate:** `accept`

**Trap:**  
Do not compare 1,702.30 directly with 124.34 without converting units.

---

### Q25 — Plan expenditure pie-chart consistency
**Severity:** EXTREME  
**Category:** image/table reasoning

**Question:**  
The Plan (Capital) Expenditure pie chart shows 70%, 9%, 6%, 5%, 5%, and 5% across its six heads. What total percentage do these categories account for? Name all six heads.

**Gold answer:**  
Total = **100%**.

Heads:
- Advance to CPWD
- Equipment & Lab Dev.
- Books & Journals
- Road & Buildings
- Adv to Supplier
- Computer, Furniture & Other

**Expected evidence:**  
Plan Account, PDF p. 340.

**Expected quality gate:** `accept`

---

# E. Infrastructure, international relations and centres

### Q26 — IIIF area comparison
**Severity:** HARD  
**Category:** calculation + location/entity relationship

**Question:**  
IIT (ISM) lists IIIF Kolkata as 16,000 sq.ft. and IIIF New Delhi as 20,000 sq.ft. What is the combined area, and what percentage of that combined area is New Delhi?

**Gold answer:**  
Combined = **36,000 sq.ft.**  
New Delhi share = `20,000 / 36,000 × 100` = **55.56%**.

**Expected evidence:**  
Section 3.8, printed p. xv (PDF p. 19).

**Expected quality gate:** `accept`

---

### Q27 — Infrastructure growth
**Severity:** HARD  
**Category:** arithmetic

**Question:**  
The institute added 17.11 lakh square feet of covered area during 2011–17 and had approximately 14.71 lakh square feet under construction. What is the combined amount, and what percentage of the completed/added amount does the in-progress area represent?

**Gold answer:**  
Combined = **31.82 lakh sq.ft.**  
In-progress / added = `14.71 / 17.11 × 100` = **85.97%**.

**Expected evidence:**  
Infrastructure development, printed p. xxiii (PDF p. 27).

**Expected quality gate:** `accept`

---

### Q28 — Research-centre counting ambiguity
**Severity:** EXTREME  
**Category:** contradiction / scope

**Question:**  
The report states that five research centres existed up to 2011, eleven new research centres were added during 2011–17, and then separately lists “Other Centres added during 2011–17” containing three named centres. What is the arithmetic total of named centres if all these categories are counted, and why must RAISE preserve the report's category distinction rather than blindly saying “19 research centres were newly added”?

**Gold answer:**  
Arithmetic total = `5 + 11 + 3 = 19` named centres/categories combined.  
However, only **11** are explicitly called “new research centres”; the three “Other Centres” are presented as a separate category. Therefore “19 research centres were newly added” is unsupported.

**Expected evidence:**  
Section 3.9, printed p. xvi (PDF p. 19).

**Expected quality gate:** `accept`

---

### Q29 — Eight-new-centres vs eleven-new-centres trap
**Severity:** ADVERSARIAL  
**Category:** contradiction detection

**Question:**  
The report's next subsection says “Establishment of eight new Research Centers as mentioned above,” while the preceding section says “Eleven new centres were added during 2011–17.” How should RAISE represent this discrepancy?

**Gold answer:**  
RAISE should **surface the discrepancy instead of silently reconciling it**. The document contains both statements. It can report that the innovation subsection refers to **eight** new Research Centers, while the preceding centre list says **eleven new centres** were added in 2011–17. The source does not explicitly resolve the difference.

**Expected evidence:**  
Printed pp. xvi–xvii (PDF pp. 19–20).

**Expected quality gate:** `accept`

---

### Q30 — Erasmus arithmetic integrity
**Severity:** VERY HARD  
**Category:** multi-row arithmetic

**Question:**  
The four Erasmus projects list mobilities of 23, 16, 3 and 9 and man-months of 194, 117, 7 and 38. Verify both totals given by the report and compute the average man-months per mobility.

**Gold answer:**  
Mobilities: `23 + 16 + 3 + 9 = 51`.  
Man-months: `194 + 117 + 7 + 38 = 356`.  
Average = `356 / 51` = **6.98 man-months per mobility** approximately.

**Expected evidence:**  
Section 7.3, printed p. xxi (PDF p. 25).

**Expected quality gate:** `accept`

---

### Q31 — Australia collaboration count discrepancy
**Severity:** EXTREME / ADVERSARIAL  
**Category:** entity counting + contradiction

**Question:**  
The report says MoUs were signed with eight Australian universities, two research organizations and one industrial partner. From the names explicitly listed immediately afterward, count the universities, research organizations and industrial partner. Does the name list exactly support the “eight universities” statement?

**Gold answer:**  
Explicitly named universities in that sentence/list:  
- Curtin University of Technology
- University of New South Wales
- University of New Castle
- University of Wollongong
- University of Western Sydney
- University of Queensland
- Monash University

= **7 universities**.

Research organizations:
- Simtars
- CSIRO

= **2**.

Industrial partner:
- **TVS-LUCAS-UGTC**

= **1**.

Thus the explicit names support **7 universities + 2 research organizations + 1 industrial partner**, not eight universities. RAISE must flag the discrepancy rather than invent an eighth university.

**Expected evidence:**  
Section 7.1, printed pp. xix–xx (PDF pp. 23–24).

**Expected quality gate:** `accept`

---

### Q32 — Missing eighth Australian university
**Severity:** ADVERSARIAL  
**Category:** unanswerability

**Question:**  
Identify the eighth Australian university referred to by the report but absent from the immediately listed university names.

**Gold answer:**  
**Unable to verify.** The report's prose says eight universities, but the immediately enumerated names provide seven universities. It does not identify a specific eighth university in that evidence.

**Expected evidence:**  
Section 7.1, printed p. xix (PDF p. 23).

**Expected quality gate:** `unable_to_verify`

**Trap:**  
Never infer that CSIRO or Simtars is a university.

---

### Q33 — 29 international collaborations: list integrity
**Severity:** EXTREME  
**Category:** entity counting

**Question:**  
The report says it established collaborations with 29 world-class universities/institutions. Count the explicitly named entities by geographic grouping and verify whether the list itself contains 29 entries.

**Gold answer:**  
America: **6**  
Australia: **10**  
Europe: **7**  
Asia and Africa: **6**  
Total = **29**, matching the report's statement.

**Expected evidence:**  
Section 7.2, printed pp. xx–xxi (PDF pp. 24–25).

**Expected quality gate:** `accept`

---

# F. Sponsored R&D project graph questions

### Q34 — Biological database mining project
**Severity:** VERY HARD  
**Category:** project → person → department → sponsor → cost

**Question:**  
Find the sponsored project whose title concerns machine-learning techniques for a specialized biological online database. Give its project number, coordinator, department, sponsor and project cost.

**Gold answer:**  
Project **CSIR(11)/2012–2013/314/CSE**.  
Coordinator: **Dr. Haider Banka**.  
Department: **Computer Science & Engineering**.  
Sponsor: **CSIR**.  
Cost: **Rs. 16.05 lakh**.

**Expected evidence:**  
Sponsored project table, printed p. 12 (PDF p. 44).

**Expected quality gate:** `accept`

---

### Q35 — Keka Ojha project cluster
**Severity:** EXTREME  
**Category:** entity-centric graph traversal + sum

**Question:**  
Identify all three sponsored projects in the 2012–2016 project tables coordinated by Dr. (Mrs.) Keka Ojha that are explicitly visible in the report. Give project number, title, sponsor and cost, then calculate their combined project cost.

**Gold answer:**  
1. **CSIR(12)/2012–2013/326** — *Development of fracturing fluid for high pressure high temperature (HPHT) reservoirs with minimum formation damage* — **CSIR** — **Rs. 14.00 lakh**.
2. **UGC(87)/2013–2014/335/PE** — *Development of Nanoparticle induced chemicals and consolidating loose formation to improve oil production* — **UGC** — **Rs. 13.23 lakh**.
3. **DST(75)/2013–2014/350/PE** — *Development of Foam based Drilling Fluid for CBM Wells* — **DST** — **Rs. 16.16 lakh**.

Combined = **Rs. 43.39 lakh**.

**Expected evidence:**  
Sponsored project tables, printed pp. 12, 14 and 18 (PDF pp. 45–50).

**Expected quality gate:** `accept`

---

### Q36 — Sagar Pal wastewater cluster
**Severity:** EXTREME  
**Category:** person → projects → themes → sponsors + sum

**Question:**  
Dr. Sagar Pal appears on two sponsored projects dealing with wastewater/materials. Identify the two projects, their sponsors and costs, and calculate the combined value.

**Gold answer:**  
- **DST(73)/2013–2014/348/AC** — *High Performance Multifunctional Modified Guar Gum for Wastewater and Industrial Effluent Treatment* — **DST** — **Rs. 24.94 lakh**.
- **DST(WTI)/(166)/2016–2017/509/AC** — *Development of Ternary Nanocomposite Hydrogel Derived from Functionalized Biopolymer Amylose/TiO2-Ag NPs and its Potential Application Towards Treatment of Wastewater* — **DST (WTI)** — **Rs. 23.90 lakh**.

Combined = **Rs. 48.84 lakh**.

**Expected evidence:**  
Sponsored project tables, printed pp. 14 and 24 (PDF pp. 46 and 56); personnel table identifies Dr. Sagar Pal with APH in the faculty list, but the project table itself carries the project departments.

**Expected quality gate:** `accept`

**Trap:**  
Do not treat the two project costs as crore amounts.

---

### Q37 — Ajay Mandal petroleum project chain
**Severity:** VERY HARD  
**Category:** person → department → projects → sponsor + sum

**Question:**  
Identify the two sponsored projects in the benchmark tables coordinated by Dr. Ajay Mandal, give sponsor/cost for each, and calculate the total.

**Gold answer:**  
- **OIL(3)/2015–2016/428/PE** — *Synthesis and extraction of surfactants from natural resources and their characterization for application in enhanced oil recovery* — **OIL** — **Rs. 22.61 lakh**.
- **DST(SERB)/(142)/2016–2017/477/PE** — *Studies on Characteristics and Dissociation Behavior of Natural Gas Hydrate in Sediments under Subsurface Mimic Conditions* — **DST(SERB)** — **Rs. 44.17 lakh**.

Total = **Rs. 66.78 lakh**.

**Expected evidence:**  
Sponsored project tables, printed pp. 19 and 24 (PDF pp. 51 and 54).

**Expected quality gate:** `accept`

---

### Q38 — Srinivasa Rao Gangumalla project pair
**Severity:** VERY HARD  
**Category:** name/entity variant + project relation + sum

**Question:**  
The personnel section lists Dr. Srinivasa Rao Gangumalla as an Assistant Professor in Applied Geophysics, while the project tables show two 2016–17 projects coordinated by him. Identify both project numbers, titles, sponsors and costs and calculate the combined cost.

**Gold answer:**  
- **DST/INSPIRE/(150)/2016–2017/486/AGP** — *Lithosphere Structure and Rheological Characteristics of the Eastern Indian Shield: Implications on Craton-mobile Belt Interactions and Crustal Growth/Recycle Processes* — **DST (INSPIRE)** — **Rs. 35.00 lakh**.
- **DST(SERB)/(164)/2016–2017/507/AGP** — *Building Crustal Models and the Delineation of Potential Concealed Mineralized Zones in the North Singhbhum Mobile Belt (NSMB) Eastern Indian Craton Through Integrated Geophysical Studies* — **DST(SERB)** — **Rs. 40.18 lakh**.

Combined = **Rs. 75.18 lakh**.

**Expected evidence:**  
Personnel, printed p. 297 (PDF p. 323) and sponsored project table, printed pp. 22 and 25 (PDF pp. 54 and 56).

**Expected quality gate:** `accept`

**Trap:**  
Do not reject the match because of minor formatting differences in the person's name.

---

### Q39 — CIL paired high-value projects
**Severity:** EXTREME  
**Category:** cross-project comparison

**Question:**  
Compare the two CIL-sponsored projects with the following titles: (1) “Studies on the use of Coal and Petcoke as Fuel in the Cement Industry in India” and (2) “Multiple Layer Trial Blasting for Better Recovery with less Diluted Coal.” Give coordinator, department, project cost for each, combined cost, and the absolute cost difference.

**Gold answer:**  
1. **Project 174** — *Studies on the use of Coal and Petcoke as Fuel in the Cement Industry in India* — Coordinator **Prof. I. M. Mishra** — **Chemical Engineering** — **Rs. 431.28 lakh**.
2. **Project 179** — *Multiple Layer Trial Blasting for Better Recovery with less Diluted Coal* — Coordinator **Prof. A. K. Mishra** — **Mining Engineering** — **Rs. 431.24 lakh**.

Combined = **Rs. 862.52 lakh**.  
Difference = **Rs. 0.04 lakh = Rs. 4,000**.

**Expected evidence:**  
Sponsored project table, printed p. 23 (PDF p. 54).

**Expected quality gate:** `accept`

---

### Q40 — ESE infrastructure project
**Severity:** VERY HARD  
**Category:** project → department → sponsor → cost

**Question:**  
Which 2016–17 project specifically augments postgraduate teaching and research facilities in the Department of Environmental Science & Engineering? Give project number, coordinator, sponsor and cost.

**Gold answer:**  
**DST(FIST)/(140)/2016–2017/471/ESE**.  
Coordinator: **Dr. Chiranjib Banerjee, Inspire Faculty**.  
Sponsor: **DST(FIST)**.  
Cost: **Rs. 144.00 lakh**.

**Expected evidence:**  
Sponsored project table, printed p. 22 (PDF p. 54).

**Expected quality gate:** `accept`

---

### Q41 — Ultra-specific antenna project
**Severity:** VERY HARD  
**Category:** exact title retrieval

**Question:**  
Identify the sponsored project for “Design and Development of Multiband Circularly Polarized Compact Metamaterial Antenna for Mobile/WLAN/WiMAX Applications.” Give project number, coordinator, department, sponsor and cost.

**Gold answer:**  
Project **DST(SERB)/(158)/2016–2017/499/ECE**.  
Coordinator: **Dr. Raghvendra Kr. Chaudhary**.  
Department: **ECE**.  
Sponsor: **DST(SERB)**.  
Cost: **Rs. 51.26 lakh**.

**Expected evidence:**  
Sponsored project table, printed p. 24 (PDF p. 56).

**Expected quality gate:** `accept`

---

### Q42 — Space-mission mathematics project
**Severity:** VERY HARD  
**Category:** title → person → department → sponsor

**Question:**  
Who coordinates the project “Energy Efficient Trajectory Design for Space Missions,” what is its project number, department, sponsor and cost?

**Gold answer:**  
Project **DST(SERB)/(163)/2016–2017/506/AM**.  
Coordinator: **Dr. Badam Singh Kushvah**.  
Department: **Applied Mathematics**.  
Sponsor: **DST(SERB)**.  
Cost: **Rs. 23.85 lakh**.

**Expected evidence:**  
Sponsored project table, printed p. 25 (PDF p. 56).

**Expected quality gate:** `accept`

---

### Q43 — Coal-fire remote-sensing chain
**Severity:** EXTREME  
**Category:** multi-hop project relationship

**Question:**  
Two 2016–17 projects concern coal-fire monitoring using remote sensing/geophysical techniques. Identify both project numbers, coordinators, departments, sponsors and costs, then compare their costs.

**Gold answer:**  
1. **ISRO/(4)/2016–2017/500/AGL** — *Estimation of Surface Deformation in Response to Fluid Extraction and Subsurface Coal Fires Using SAR Interferometric Techniques* — **Dr. Tajdarul H. Syed**, **Applied Geology**, **ISRO**, **Rs. 22.70 lakh**.
2. **ISRO/(5)/2016–2017/502/ME** — *Thermal Anomaly Reduction and Monitoring of Coal Fire in the Gondwana Coal Fields and Coal Fire Induced Land Subsidence Using Remote Sensing and Ground Based Techniques* — **Dr. Dheeraj Kumar**, **Mining Engineering**, **ISRO**, **Rs. 19.39 lakh**.

Difference = **Rs. 3.31 lakh**; project 500 is higher.

**Expected evidence:**  
Sponsored project table, printed pp. 24–25 (PDF p. 56).

**Expected quality gate:** `accept`

---

### Q44 — Wastewater and Ganga project comparison
**Severity:** EXTREME  
**Category:** cross-project semantic matching + numeric comparison

**Question:**  
Compare the project on ternary nanocomposite hydrogel for wastewater treatment with the Prime Minister's Namami Gange project. Give coordinators, departments, sponsors, costs and the difference in cost.

**Gold answer:**  
Wastewater hydrogel project: **DST(WTI)/(166)/2016–2017/509/AC**, coordinator **Dr. Sagar Pal**, Department of **Applied Chemistry**, **DST(WTI)**, **Rs. 23.90 lakh**.  
Namami Gange project: **MHRD(Namami Gange)/2016–2017/472/ISM**, coordinator **Prof. I. M. Mishra**, Department of **Chemical Engineering**, **MHRD (Namami Gange)**, **Rs. 5.00 lakh**.  
Difference = **Rs. 18.90 lakh**.

**Expected evidence:**  
Sponsored project table, printed pp. 22 and 25 (PDF pp. 54 and 56).

**Expected quality gate:** `accept`

---

### Q45 — Project-number provenance challenge
**Severity:** EXTREME  
**Category:** exact identifier retrieval

**Question:**  
For each of the following project titles, return the exact project number and sponsor:  
(a) “Development of an Intelligent Helmet for Safety and Communication of Underground Miners”  
(b) “Development of a Selection Methodology for Roadheader and Tunnel Boring Machine in Different Geological Conditions for Rapid Tunnelling.”

**Gold answer:**  
(a) **DST(SERB)/(144)/2016–2017/480/MME** — **DST(SERB)**.  
(b) **CPRI/2016–2017/492/ME** — **CPRI**.

**Expected evidence:**  
Sponsored project table, printed pp. 24–25 (PDF p. 55).

**Expected quality gate:** `accept`

---

# G. Person-centric multi-hop questions

### Q46 — Vishnu Priye three-hop chain
**Severity:** EXTREME  
**Category:** person → role → project → Ph.D.

**Question:**  
Find the person who, in the 2016–17 personnel section, served as **Dean (Research & Development)**, belonged to ECE as a professor, coordinated the “Optical Sensors Based Traffic Weighbridge” project, and also appears as a Ph.D. guide in the research-degree table. Name the person and give the project number, project cost, and the Ph.D. candidate identified in that table.

**Gold answer:**  
Person: **Prof. Vishnu Priye**.  
Project: **DST(SERB)/(162)/2016–2017/505/ECE**, *Optical Sensors Based Traffic Weighbridge*, cost **Rs. 42.39 lakh**.  
Ph.D. candidate: **Jitendra Kumar Mishra**, whose Ph.D. entry lists Prof. Vishnu Priye as guide.

**Expected evidence:**  
Personnel, printed p. 289 (PDF p. 319); sponsored project table, printed p. 24 (PDF p. 56); Ph.D. table, printed p. 27 (PDF around p. 61).

**Expected quality gate:** `accept`

**Trap:**  
Do not confuse Prof. Vishnu Priye with Dr. Vishnu Kumar or Prof. V. Kumar.

---

### Q47 — Dr. Sushrut Das cross-domain relation
**Severity:** VERY HARD  
**Category:** person → sponsored project → Ph.D. guide

**Question:**  
Identify the electronics professor who coordinated the project “To augment the research facilities in the deptt of Electronics Engineering, ISM, Dhanbad.” Give the project number/cost and identify one Ph.D. student in the report for whom the same person is listed as guide.

**Gold answer:**  
Coordinator: **Dr. Sushrut Das**.  
Project: **DST(72)/2013–2014/344/ECE**.  
Cost: **Rs. 120.00 lakh**.  
One matching Ph.D. entry: **Rakesh Kumar Yadav** lists **Dr. Sushrut Das (Guide)** for *Microwave Rectennas Integrated with Microstrip …*.

**Expected evidence:**  
Sponsored project table, printed p. 14 (PDF p. 46); Ph.D. table, printed p. 27 (PDF p. 59).

**Expected quality gate:** `accept`

---

### Q48 — Prof. A. K. Mishra identity collision test
**Severity:** EXTREME  
**Category:** name disambiguation

**Question:**  
The report contains multiple people with similar initials. Distinguish these two entities: **Prof. A. K. Mishra, Associate Dean (International Relations & Alumni Affairs)** and **Prof. A. K. Mishra, Mining Engineering project coordinator**. Are they presented as the same person in the report?

**Gold answer:**  
The report itself presents **Prof. A. K. Mishra** as Associate Dean (IR&AA) in the personnel section and also lists **Prof. A. K. Mishra** as coordinator of the CIL-sponsored Mining Engineering project 179. The report does not introduce a second disambiguated A. K. Mishra identity in those specific entries. Therefore RAISE should treat them as the **same named entity unless another source segment explicitly distinguishes them**, while preserving the uncertainty caused by the identical initials/name.

**Expected evidence:**  
Personnel, printed p. 289 (PDF p. 319); sponsored project table, printed p. 23 (PDF p. 54).

**Expected quality gate:** `accept`

**Trap:**  
Do not invent a second A. K. Mishra merely because name collisions are possible in principle.

---

### Q49 — Dr. Haider Banka graph join
**Severity:** VERY HARD  
**Category:** person → faculty role → project → Ph.D. guide

**Question:**  
Dr. Haider Banka is an Associate Professor in CSE. Which sponsored project in the report does he coordinate, and which Ph.D. candidate lists him as guide? Give the project cost and thesis title for the Ph.D. candidate.

**Gold answer:**  
Sponsored project: **CSIR(11)/2012–2013/314/CSE**, *Design of machine learning techniques for specialized biological online database-mining*, **Rs. 16.05 lakh**, sponsor **CSIR**.  
A Ph.D. entry lists **Mohammad Nadeem** with **Dr. Haider Banka (Guide)** and thesis *Designing Soft Computing Techniques for Parameter Estimation and Optimization in Green Pelletization*.

**Expected evidence:**  
Sponsored project table, printed p. 12 (PDF p. 44); personnel, printed p. 292 (PDF p. 322); Ph.D. table, printed p. 39 (PDF p. 63).

**Expected quality gate:** `accept`

---

### Q50 — Same sponsor, different scientific domains
**Severity:** EXTREME  
**Category:** graph reasoning + classification

**Question:**  
Identify two different 2016–17 sponsored projects funded by ISRO in different departments: one involving SAR interferometric techniques for surface deformation/subsurface coal fires and one involving thermal anomaly reduction and coal-fire monitoring. Explain the department-level distinction and cost difference.

**Gold answer:**  
- **Project 500**, Applied Geology, Dr. Tajdarul H. Syed, Rs. **22.70 lakh**.
- **Project 502**, Mining Engineering, Dr. Dheeraj Kumar, Rs. **19.39 lakh**.
- Cost difference = **Rs. 3.31 lakh**.
- Both are ISRO-sponsored, but one belongs to **Applied Geology** and the other to **Mining Engineering**.

**Expected evidence:**  
Sponsored project table, printed p. 24–25 (PDF p. 56).

**Expected quality gate:** `accept`

---

# H. International partnership and technology multi-hop questions

### Q51 — AICCET partner intersection
**Severity:** EXTREME  
**Category:** multi-hop entity intersection

**Question:**  
The report says the Australia–India Centre for Clean Coal and Energy Technologies (AICCET) was established at IIT (ISM) Dhanbad and several Australian institutions. Name every institution explicitly tied to AICCET in the sentence and identify which of those also appear in the broader Australian collaboration list.

**Gold answer:**  
AICCET is stated as established at:
- **IIT (ISM) Dhanbad**
- **Curtin University**
- **University of Queensland**
- **University of New Castle**
- **CSIRO**

All four Australian entities also appear in the broader Australian collaboration list.

**Expected evidence:**  
Section 7.1, printed p. xx (PDF p. 24) and Australian collaboration list, printed pp. xx–xxi (PDF pp. 24–25).

**Expected quality gate:** `accept`

---

### Q52 — CEMT and VRMS relationship
**Severity:** VERY HARD  
**Category:** semantic relationship

**Question:**  
Which research centre was established in collaboration with Australian institutions for Advanced Mining Technology and Mines Safety, and what unique facility was being developed under it?

**Gold answer:**  
**Centre of Excellence in Mining Technology (CEMT)**; under it, a **Virtual Reality Mine Simulator (VRMS)** was being developed at IIT (ISM) Dhanbad.

**Expected evidence:**  
Section 7.1, printed p. xx (PDF p. 24).

**Expected quality gate:** `accept`

---

### Q53 — Manganese discovery implied valuation
**Severity:** EXTREME  
**Category:** unit conversion + derived metric

**Question:**  
The report describes the largest-ever manganese ore deposit as about 30 million tonnes with an estimated value of Rs. 36,000 crore. What implied value per million tonnes does the report's arithmetic correspond to?

**Gold answer:**  
`36,000 crore / 30 million tonnes` = **1,200 crore per million tonnes**.

**Expected evidence:**  
Executive Summary, printed p. xviii (PDF p. 22).

**Expected quality gate:** `accept`

**Trap:**  
This is a derived metric, not a value explicitly stated by the report.

---

### Q54 — Uranium-mine technology specificity
**Severity:** HARD  
**Category:** entity + quantitative relation

**Question:**  
What technology was designed to reduce radiation dose in underground mines, for which organization, how many mines were explicitly covered, and to what depth?

**Gold answer:**  
**Design and implementation of a mine ventilation system for reduction in radiation dose**, for the **Uranium Corporation of India Ltd. (UCIL)**, covering **all seven underground mines**, operating up to **940 m depth** from the surface.

**Expected evidence:**  
Executive Summary technology list, printed pp. xviii–xix (PDF pp. 22–23).

**Expected quality gate:** `accept`

---

# I. Research-degree and departmental graph questions

### Q55 — Ph.D. thesis/domain linkage
**Severity:** VERY HARD  
**Category:** exact name + guide + discipline

**Question:**  
Who was awarded the Ph.D. for “Designing Soft Computing Techniques for Parameter Estimation and Optimization in Green Pelletization”? Give the date, department and guide(s).

**Gold answer:**  
Candidate: **Mohammad Nadeem**.  
Date: **14.01.2017**.  
Department: **Computer Science and Engineering**.  
Guide(s): **Dr. Haider Banka (Guide) & Prof. R. Venugopal (Co-Guide)**.

**Expected evidence:**  
Research-degree table, printed p. 39 (PDF p. 63).

**Expected quality gate:** `accept`

---

### Q56 — Ph.D. candidate to project-connected faculty
**Severity:** EXTREME  
**Category:** multi-hop

**Question:**  
Find a Ph.D. candidate whose guide is Dr. S. K. Raghuwanshi and whose thesis concerns MEMS pressure-sensor dynamic range. Give candidate, department, date and the relevant project connection for the same faculty member, if one is explicitly documented in the sponsored-project table.

**Gold answer:**  
Candidate: **Sumit Kumar Jindal**.  
Date: **08.02.2017**.  
Department: **Electronics Engineering**.  
Guide: **Dr. S. K. Raghuwanshi**.  
The sponsored-project evidence in the benchmark does not establish a specific Raghuwanshi-led project number/cost for a direct second-hop connection. Therefore the project connection should **not be invented**.

**Expected evidence:**  
Ph.D. table, printed p. 33 (PDF p. 64); personnel/project sections.

**Expected quality gate:** `unable_to_verify`

**Trap:**  
This is deliberately designed to punish “name appears somewhere” graph joining.

---

# J. Negative and hallucination traps

### Q57 — Unsupported ranking
**Severity:** ADVERSARIAL  
**Category:** unanswerability

**Question:**  
Which single 2016–17 sponsored project was the institute's most expensive project of the entire year?

**Gold answer:**  
**Unable to verify from the supplied evidence set without exhaustively resolving every project row and all relevant project-cost entries.** RAISE must not declare a global maximum based only on a handful of highly visible rows such as Projects 174 and 179.

**Expected quality gate:** `unable_to_verify`

---

### Q58 — Unsupported causation
**Severity:** ADVERSARIAL  
**Category:** causal hallucination

**Question:**  
Did the establishment of the Central Research Facility directly cause SCOPUS publications to rise from 156 in 2010 to 1,237 in 2016?

**Gold answer:**  
**Unable to verify.** The report describes CRF establishment and publication growth, but it does not establish a direct causal relationship between them.

**Expected quality gate:** `unable_to_verify`

**Trap:**  
Correlation/temporal co-occurrence is not documented causation.

---

### Q59 — Unsupported missing entity
**Severity:** ADVERSARIAL  
**Category:** entity hallucination

**Question:**  
What was the exact name of the eighth Australian university omitted from the collaboration list?

**Gold answer:**  
**Unable to verify.** The source says eight universities but explicitly lists seven. No eighth name is supplied in the cited passage.

**Expected quality gate:** `unable_to_verify`

---

### Q60 — Definition collision
**Severity:** EXTREME / ADVERSARIAL  
**Category:** semantic disambiguation

**Question:**  
Can RAISE state that “research scholars” and “students” are the same population in this report because the research-scholar total is close to the difference between the detailed academic tables and the headline student-strength number?

**Gold answer:**  
**No.** The report does not establish that equivalence. “Research scholars” is reported separately, and the detailed academic tables do not provide a complete reconciliation to the 7,903 headline total. RAISE should not convert numerical closeness into identity.

**Expected quality gate:** `unable_to_verify`

---

# K. Extreme composite questions for end-to-end RAISE

### Q61 — Four-hop R&D synthesis
**Severity:** EXTREME  
**Category:** multi-hop graph + calculation

**Question:**  
Starting from **Applied Chemistry**, identify the faculty member who appears on both (a) a DST-funded project on modified guar gum for wastewater/industrial effluent treatment and (b) a DST WTI-funded project on a ternary nanocomposite hydrogel for wastewater treatment. Give both titles, project numbers, costs, total cost, and the faculty member's designation in the personnel section.

**Gold answer:**  
Faculty member: **Dr. Sagar Pal**, Associate Professor (personnel section; listed as APH in the personnel table even though the cited project rows are categorized under Applied Chemistry).  
Projects:
- **DST(73)/2013–2014/348/AC** — modified guar gum for wastewater/industrial effluent treatment — **Rs. 24.94 lakh**.
- **DST(WTI)/(166)/2016–2017/509/AC** — ternary nanocomposite hydrogel for wastewater treatment — **Rs. 23.90 lakh**.
Total = **Rs. 48.84 lakh**.

**Expected evidence:**  
Sponsored projects, printed pp. 14 and 25 (PDF pp. 46 and 56); personnel, printed p. 292 (PDF p. 322).

**Expected quality gate:** `accept`

**Important trap:**  
Do not silently rewrite the personnel department as Applied Chemistry; the personnel table explicitly lists **APH** for Dr. Sagar Pal.

---

### Q62 — Five-hop international research chain
**Severity:** EXTREME  
**Category:** graph intersection + exact entity retrieval

**Question:**  
Which collaboration chain connects IIT (ISM) to the clean-coal programme, the Australia–India Centre of Excellence/AICCET ecosystem, and Curtin University? Name the relevant centre, the shared university and the associated research theme.

**Gold answer:**  
The relevant centre is **Australia–India Joint Research Centre for Clean Coal and Energy Technology / Australia–India Centre for Clean Coal and Energy Technologies (AICCET)**.  
Shared university: **Curtin University of Technology / Curtin University**.  
Theme: **Energy and Clean Coal Technologies**, with related mines-safety/collaborative research described in the report.

**Expected evidence:**  
Centres of Advanced Learning and international relations sections, printed pp. xvi, xix–xx (PDF pp. 19, 23–24).

**Expected quality gate:** `accept`

---

### Q63 — Compound growth consistency challenge
**Severity:** EXTREME  
**Category:** multiple calculations

**Question:**  
For each metric below, recompute endpoint growth and classify the report as “consistent after rounding” or “discrepant”:  
1. SCOPUS publications: 156 → 1,237, reported 688%.  
2. WoS publications: 113 → 1,057, reported 836%.  
3. Research scholars: 225 → 1,894, reported 742%.  
4. Ph.D. degrees: 22 → 167, reported 659%.  
5. Project outlay: 21.98 → 124.34 crore, reported 466%.

**Gold answer:**  
1. SCOPUS = **692.95%** → **discrepant** with 688%.  
2. WoS = **835.40%** → **consistent after rounding** to 836%.  
3. Research scholars = **741.78%** → **consistent after rounding** to 742%.  
4. Ph.D. degrees = **659.09%** → **consistent after rounding** to 659%.  
5. Project outlay = **465.70%** → **consistent after rounding** to 466%.

**Expected quality gate:** `accept`

---

### Q64 — Financial + R&D unit-conversion chain
**Severity:** EXTREME  
**Category:** cross-section arithmetic

**Question:**  
Compare three 2016–17 values expressed in different units: (a) Rs. 124.34 crore sponsored project outlay, (b) Rs. 1,702.30 lakh consultancy value, and (c) Rs. 7,885.86 lakh Plan capital-asset expenditure. Convert all three to crore and rank them.

**Gold answer:**  
(a) Sponsored project outlay = **Rs. 124.34 crore**.  
(b) Consultancy = **Rs. 17.023 crore**.  
(c) Plan capital-asset expenditure = **Rs. 78.8586 crore**.

Ranking:  
**Sponsored project outlay (124.34 cr) > Plan capital-asset expenditure (78.8586 cr) > Consultancy (17.023 cr)**.

**Expected evidence:**  
Project outlay: printed p. 13 (PDF p. 17).  
Consultancy: printed p. 199 (PDF p. 229).  
Plan Account: PDF p. 340.

**Expected quality gate:** `accept`

---

### Q65 — The “looks answerable but isn't” challenge
**Severity:** ADVERSARIAL  
**Category:** source-bounded reasoning

**Question:**  
Which exact eighth Australian university signed an MoU with IIT (ISM), and what was the rupee value of its corresponding sponsored project in 2016–17?

**Gold answer:**  
**Unable to verify.** The source passage does not name an eighth Australian university, and therefore no defensible mapping to a unique sponsored project can be made.

**Expected quality gate:** `unable_to_verify`

---

# Recommended RAISE evaluation assertions

For this benchmark, do not grade only final-answer string similarity. A strong result should satisfy all of the following where applicable:

```text
RETRIEVAL
- Correct source document
- Correct section
- Correct page(s)
- Correct table/project row

ENTITY LINKING
- Person ↔ role
- Person ↔ department
- Person ↔ project
- Project ↔ sponsor
- Project ↔ cost
- Person ↔ Ph.D. candidate
- Person ↔ thesis
- Institution ↔ collaboration
- Centre ↔ partner institution

NUMERICAL QA
- Correct unit conversion
- Correct formula
- Correct arithmetic
- Correct rounding
- Clear separation of reported vs recomputed figures

GROUNDING
- Every externally verifiable factual claim has evidence
- No unsupported name completion
- No silent contradiction repair
- No causal inference without textual support

NEGATIVE QA
- `unable_to_verify` when the requested entity/value cannot be proven
- No “best guess” completion
- No use of unstated world knowledge to bridge a missing source fact

GRAPH QA
- At least 2-hop correctness for hard questions
- 3+ hop correctness for extreme questions
- No false joins caused by similar names
- No entity merge based only on superficial name similarity

TRACEABILITY
- Page-level citation should point to the smallest useful evidence span
- For table questions, cite the actual table page/row, not only the chapter opening page
- For composite questions, cite every independent evidence location
```

# Suggested automatic scoring

A practical per-question score can be:

```text
2.0  Correct final answer
1.0  Correct arithmetic / derivation
1.0  Correct entity relationships
1.0  Correct citation/page grounding
1.0  Correct quality-gate decision
1.0  Correctly identifies contradiction/ambiguity when present
1.0  Avoids unsupported inference
= 8.0 points per question
```

For `unable_to_verify` questions, award full correctness only when RAISE both:
1. refuses to invent the missing fact, and
2. explains exactly which evidence is insufficient.

# High-risk failure patterns this benchmark is intended to expose

1. **Citation laundering:** citing a chapter page instead of the page containing the actual row.
2. **Arithmetic hallucination:** accepting a report's displayed percentage without recomputation.
3. **Silent correction:** replacing a source's 688% SCOPUS figure with the recomputed 692.95% without noting the discrepancy.
4. **Entity completion:** inventing the missing eighth Australian university.
5. **False graph merge:** treating similarly named professors as distinct or identical without evidence.
6. **False equivalence:** treating research scholars as automatically identical to the unexplained difference in overall student strength.
7. **Unit collision:** mixing lakh and crore without conversion.
8. **Global-max hallucination:** declaring a project the “largest” without checking the full project table.
9. **Causal hallucination:** converting temporal association into documented causation.
10. **Partial-evidence overclaim:** answering a compound question when one required hop has no source support.
