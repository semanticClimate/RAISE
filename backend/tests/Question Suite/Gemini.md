# RAISE-Bench-V1

## Tier 1: Exact Table Metrics

---
### Q_01 Tier: Tier 1
- **Target Document**: Annual Report 2024-25 final upload.pdf (Page 22, Administration)
- **Question**: What is the total number of Administrative Staff appointed at IIT Madras during the academic year 2024-25?
- **Ground Truth Answer**: 307
- **Required Keywords/Entities**: [Administrative Staff, 307, IIT Madras]
- **NotebookLM Answer**: According to the Administration section of the IIT Madras Annual Report 2024-25, there are 307 Administrative Staff positions [cite: 1].
---

---
### Q_02 Tier: Tier 1
- **Target Document**: AR_2024-25_Combined_English_Mail.pdf (Page 10, Admissions)
- **Question**: How many female students were admitted to the 4 Year Bachelor of Technology program in the academic year 2024-25 at IIT (ISM) Dhanbad?
- **Ground Truth Answer**: 191
- **Required Keywords/Entities**: [Female students, 191, Bachelor of Technology]
- **NotebookLM Answer**: In the academic year 2024-25, 191 female students were admitted to the 4 Year Bachelor of Technology program at IIT (ISM) Dhanbad [cite: 2].
---

---
### Q_03 Tier: Tier 1
- **Target Document**: ARE-2016-17.pdf (Page 6, 2.1 Undergraduate Programmes)
- **Question**: What was the total sanctioned strength for the Computer Science & Engineering undergraduate program in the 2016-17 academic year?
- **Ground Truth Answer**: 103
- **Required Keywords/Entities**: [Computer Science & Engineering, Sanctioned Strength, 103]
- **NotebookLM Answer**: The total sanctioned strength for the Computer Science & Engineering undergraduate program during the 2016-17 academic year was 103 [cite: 3].
---

---
### Q_04 Tier: Tier 1
- **Target Document**: IITMRP Annual Report.pdf (Page 29, Energy & Sustainability)
- **Question**: What is the capacity of the Rooftop Solar installation at the IIT Madras Research Park?
- **Ground Truth Answer**: 1 MW
- **Required Keywords/Entities**: [Rooftop Solar, 1 MW, Energy Profile]
- **NotebookLM Answer**: The Rooftop Solar installation at the IIT Madras Research Park has a capacity of 1 MW [cite: 4].
---

## Tier 2: Multi-Hop Entity Relationships

---
### Q_05 Tier: Tier 2
- **Target Document**: Annual Report 2024-25 final upload.pdf (Page 16, 1.3) & IITMRP Annual Report.pdf (Page 13, Mindgrove)
- **Question**: Identify the IIT Madras alumnus and co-founder of Ather Energy who is mentioned in the IIT Madras 2024-25 Director's Report, and name the IITMRP-incubated startup developing the Secure IoT microcontroller chip based on the SHAKTI processor.
- **Ground Truth Answer**: Tarun Mehta (and Swapnil Jain) co-founded Ather Energy. Mindgrove is the startup developing the Secure IoT microcontroller chip.
- **Required Keywords/Entities**: [Tarun Mehta, Swapnil Jain, Mindgrove, Secure IoT]
- **NotebookLM Answer**: Tarun Mehta and Swapnil Jain, IIT Madras alumni, co-founded Ather Energy, which was IITMIC's first IPO-listed company [cite: 1]. Additionally, Mindgrove is the startup incubated at IITMRP that is developing the Secure IoT microcontroller chip based on the SHAKTI Processor [cite: 4].
---

---
### Q_06 Tier: Tier 2
- **Target Document**: AR_2024-25_Combined_English_Mail.pdf (Page 9, Rankings) & ARE-2016-17.pdf (Page 10, 2.5 Research Programme)
- **Question**: Compare the total number of enrolled research scholars at IIT (ISM) Dhanbad in the academic year 2016-17 with the NIRF Engineering rank achieved by the institute in 2024-25.
- **Ground Truth Answer**: The number of research scholars in 2016-17 was 1894. The NIRF Engineering rank in 2024-25 was 15.
- **Required Keywords/Entities**: [1894, NIRF Engineering Rank, 15]
- **NotebookLM Answer**: In the academic year 2016-17, IIT (ISM) Dhanbad had a total of 1894 research scholars enrolled [cite: 3]. In the 2024-25 rankings, the institute achieved the 15th position in the NIRF Engineering category [cite: 2].
---

---
### Q_07 Tier: Tier 2
- **Target Document**: Annual Report 2024-25 final upload.pdf (Page 15, 1.2.4 & Page 12, 1.2.1)
- **Question**: Which Shanti Swarup Bhatnagar Award winner from IIT Madras also mentors the startups Terraclime and BotForge?
- **Ground Truth Answer**: Dr. Prabhu Rajagopal
- **Required Keywords/Entities**: [Dr. Prabhu Rajagopal, Shanti Swarup Bhatnagar Award, Terraclime]
- **NotebookLM Answer**: Dr. Prabhu Rajagopal won the Shanti Swarup Bhatnagar Award [cite: 1]. He also mentors startups including Terraclime and BotForge [cite: 1].
---

---
### Q_08 Tier: Tier 2
- **Target Document**: IITMRP Annual Report.pdf (Page 8, Board of Directors & Page 16, India Centre for Lab Grown Diamond)
- **Question**: Who serves as the Secretary to Government, Industries, Investment Promotion & Commerce Department on the IITMRP Board of Directors, and what specific workshop was hosted by the India Centre for Lab Grown Diamond?
- **Ground Truth Answer**: V Arun Roy, IAS is the Secretary. The workshop hosted was "VAIRAM".
- **Required Keywords/Entities**: [V Arun Roy, VAIRAM, Board of Directors]
- **NotebookLM Answer**: V Arun Roy, IAS, serves as the Secretary to Government, Industries, Investment Promotion & Commerce Department on the IITMRP Board [cite: 4]. The India Centre for Lab Grown Diamond hosted a workshop named VAIRAM to explore advancements in the lab-grown diamond sector [cite: 4].
---

## Tier 3: Longitudinal Trend Analysis

---
### Q_09 Tier: Tier 3
- **Target Document**: ARE-2016-17.pdf (Page 13, 3.3 Sponsored Research Projects)
- **Question**: Calculate the overall percentage growth in Sponsored Research and Industrial Project Outlay from the base year 2010-11 to the year 2016-17 at IIT (ISM) Dhanbad, and provide the exact outlay amounts for both years.
- **Ground Truth Answer**: Overall growth is 466%. Outlay in 2010-11 was Rs. 21.98 Crores and in 2016-17 it was Rs. 124.34 Crores.
- **Required Keywords/Entities**: [466%, 21.98 Crores, 124.34 Crores]
- **NotebookLM Answer**: The Sponsored Research and Industrial Project Outlay at IIT (ISM) Dhanbad grew by 466% over the six-year period [cite: 3]. The outlay was Rs. 21.98 Crores in the base year 2010-11 and increased to Rs. 124.34 Crores in 2016-17 [cite: 3].
---

---
### Q_10 Tier: Tier 3
- **Target Document**: ARE-2016-17.pdf (Page 42, Table 3.4)
- **Question**: What was the per faculty publication rate in the Web of Science (WoS) database for the years 2010 and 2016 at IIT (ISM) Dhanbad, and what was the overall growth percentage?
- **Ground Truth Answer**: Per faculty publication was 0.61 in 2010 and 3.72 in 2016. Overall growth was 836%.
- **Required Keywords/Entities**: [0.61, 3.72, 836%]
- **NotebookLM Answer**: At IIT (ISM) Dhanbad, the per faculty publication in the Web of Science database was 0.61 in 2010 and rose to 3.72 in 2016 [cite: 3]. This represents an overall growth of 836% over the period [cite: 3].
---

---
### Q_11 Tier: Tier 3
- **Target Document**: AR_2024-25_Combined_English_Mail.pdf (Page 22, 3.2 Sponsored Research Projects)
- **Question**: How much did the total amount sanctioned for new R&D projects increase (in INR) between the financial year 2023-24 and 2024-25?
- **Ground Truth Answer**: It increased from Rs. 37,73,00,000.00 in 2023-24 to Rs. 161,03,71,316.00 in 2024-25 (an increase of Rs. 123,30,71,316).
- **Required Keywords/Entities**: [37,73,00,000.00, 161,03,71,316.00, Increase]
- **NotebookLM Answer**: The total amount sanctioned for new R&D projects at IIT (ISM) Dhanbad increased significantly from Rs. 37,73,00,000 in the 2023-24 financial year to Rs. 161,03,71,316 in 2024-25 [cite: 2].
---

---
### Q_12 Tier: Tier 3
- **Target Document**: AR_2024-25_Combined_English_Mail.pdf (Page 22, 3.1 Research Publications)
- **Question**: Trace the trend in the number of research publications indexed in SCOPUS for the years 2022, 2023, and 2024 at IIT (ISM) Dhanbad.
- **Ground Truth Answer**: 1818 in 2022; 1661 in 2023; 1614 in 2024.
- **Required Keywords/Entities**: [1818, 1661, 1614, SCOPUS]
- **NotebookLM Answer**: The number of research publications indexed in SCOPUS for IIT (ISM) Dhanbad was 1818 in the year 2022, decreased to 1661 in 2023, and further decreased to 1614 in the year 2024 [cite: 2].
---

## Tier 4: Unanswerable / Hallucination Traps

---
### Q_13 Tier: Tier 4
- **Target Document**: Annual Report 2024-25 final upload.pdf (Page 18, 1.6 Infrastructure Development)
- **Question**: What is the exact budget allocated for the construction of the new 800-bed girls' hostel mentioned in the Future Infrastructure Development plan at IIT Madras?
- **Ground Truth Answer**: The document mentions the proposal for an 800-bed new girls' hostel but does not provide the exact budget allocated for it.
- **Required Keywords/Entities**: [800-bed girls' hostel, Budget, Unanswerable]
- **NotebookLM Answer**: The Annual Report 2024-25 for IIT Madras mentions the proposal to construct an 800-bed new girls' hostel as a future infrastructure project, but it does not specify the exact budget allocated for its construction [cite: 1].
---

---
### Q_14 Tier: Tier 4
- **Target Document**: IITMRP Annual Report.pdf (Page 14, NeoMotion)
- **Question**: How many patents were successfully granted to the startup "NeoMotion" during the financial year 2024-25?
- **Ground Truth Answer**: The document highlights NeoMotion's success and beneficiary numbers but does not state the number of patents granted to them in FY 2024-25.
- **Required Keywords/Entities**: [NeoMotion, Patents granted, Unanswerable]
- **NotebookLM Answer**: The IITMRP Annual Report details NeoMotion's achievements, such as supporting over 11,500 beneficiaries and launching NeoStand [cite: 4], but it does not provide information regarding the specific number of patents granted to the startup in FY 2024-25.
---

---
### Q_15 Tier: Tier 4
- **Target Document**: AR_2024-25_Combined_English_Mail.pdf (Page 51, 4.4 ACIC IIT (ISM) Foundation)
- **Question**: What was the exact amount of CSR funding received from Reliance Industries for the ACIC IIT (ISM) Foundation in 2024?
- **Ground Truth Answer**: The document does not mention any CSR funding received from Reliance Industries for the ACIC IIT (ISM) Foundation.
- **Required Keywords/Entities**: [Reliance Industries, CSR funding, ACIC IIT (ISM) Foundation, Unanswerable]
- **NotebookLM Answer**: The provided IIT (ISM) Dhanbad Annual Report 2024-25 does not mention any CSR funding provided by Reliance Industries to the ACIC IIT (ISM) Foundation [cite: 2].
---

---
### Q_16 Tier: Tier 4
- **Target Document**: ARE-2016-17.pdf (Page 13, 3.3 Sponsored Research Projects)
- **Question**: Name the principal investigator for the "Smart City Intelligent Traffic Management" project funded by the Ministry of Urban Development at IIT (ISM) Dhanbad in 2016-17.
- **Ground Truth Answer**: There is no such project listed under the sponsored research projects in the 2016-17 Annual Report.
- **Required Keywords/Entities**: [Smart City Intelligent Traffic Management, Ministry of Urban Development, Unanswerable]
- **NotebookLM Answer**: A thorough review of the sponsored research projects in the IIT (ISM) Dhanbad Annual Report 2016-17 reveals no mention of a "Smart City Intelligent Traffic Management" project funded by the Ministry of Urban Development [cite: 3]. Therefore, no principal investigator can be named.
---
