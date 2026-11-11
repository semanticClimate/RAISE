"""
RAISE Academic GraphRAG Studio - System Synthesis Prompt Module
Formatted for optimal LLM adherence (Qwen 2.5, GPT-4, Claude, LLaMA)
with clear semantic boundaries, citation formatting, and anti-hallucination guardrails.
"""

import re
from typing import Any, Dict, List, Optional


def clean_repetitive_citations(text: str) -> str:
    """
    Cleans repetitive and cluttered inline citations.
    1. If an intro header (ending with ':') has citation [N], strips [N] from child bullets.
    2. If all child bullets share the same citation [N] and intro ends with ':',
       promotes [N] to the intro line and strips [N] from child bullets.
    3. If a list of bullets shares the exact same citation [N] without an intro, keeps [N]
       on the first bullet and strips it from subsequent consecutive bullets.
    4. Removes duplicate identical citations within the same line (e.g. [1] ... [1] -> ... [1]).
    """
    if not text:
        return ""

    lines = text.split("\n")
    # Match trailing citation e.g. [1], [1, 2], [1]., etc.
    cit_pattern = r"\s*(\[(\d+(?:,\s*\d+)*)\])\s*\.?\s*$"

    # Pass 1: Collapse duplicate identical citations within any single line
    for idx, line in enumerate(lines):
        cits_in_line = re.findall(r"\[(\d+)\]", line)
        if len(cits_in_line) > 1 and len(set(cits_in_line)) == 1:
            c_tag = f"[{cits_in_line[0]}]"
            parts = line.split(c_tag)
            lines[idx] = "".join(parts[:-1]) + c_tag + parts[-1]

    # Pass 2: Process blocks of bullets and their headers
    i = 0
    while i < len(lines):
        line = lines[i]
        is_bullet = bool(re.match(r"^\s*(?:•|\*|-|\d+\.)\s+", line))

        if is_bullet:
            bullet_start = i
            bullet_indices = []
            while i < len(lines):
                b_line = lines[i]
                if not b_line.strip():
                    if i + 1 < len(lines) and re.match(r"^\s*(?:•|\*|-|\d+\.)\s+", lines[i + 1]):
                        i += 1
                        continue
                    else:
                        break
                if re.match(r"^\s*(?:•|\*|-|\d+\.)\s+", b_line):
                    bullet_indices.append(i)
                    i += 1
                else:
                    break

            if len(bullet_indices) >= 2:
                bullet_cits = []
                for b_idx in bullet_indices:
                    m = re.search(cit_pattern, lines[b_idx])
                    bullet_cits.append(m.group(1).strip() if m else None)

                non_empty = [c for c in bullet_cits if c is not None]
                if non_empty and len(set(non_empty)) == 1:
                    common_cit = non_empty[0]

                    prev_idx = bullet_start - 1
                    while prev_idx >= 0 and not lines[prev_idx].strip():
                        prev_idx -= 1

                    has_intro = (prev_idx >= 0 and lines[prev_idx].strip().endswith(":"))

                    if has_intro:
                        intro_line = lines[prev_idx]
                        if common_cit in intro_line:
                            for b_idx in bullet_indices:
                                lines[b_idx] = re.sub(rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx])
                        else:
                            colon_idx = intro_line.rfind(":")
                            lines[prev_idx] = f"{intro_line[:colon_idx].rstrip()} {common_cit}:"
                            for b_idx in bullet_indices:
                                lines[b_idx] = re.sub(rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx])
                    else:
                        first_kept = False
                        for b_idx in bullet_indices:
                            if common_cit in lines[b_idx]:
                                if not first_kept:
                                    first_kept = True
                                else:
                                    lines[b_idx] = re.sub(rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx])
            continue
        i += 1

    return "\n".join(lines)


def sanitize_rag_text(text: str) -> str:
    """
    Sanitizes RAG text, stripping control characters, normalizing newlines,
    and ensuring bullet points, lists, and paragraphs are formatted cleanly for
    both terminal and web frontends. Automatically attributes entity roles and
    structures bullet points with blank line spacing to prevent paragraph collapsing.
    """
    if not text:
        return ""
    # Strip non-printable control characters (ASCII 0-8, 11, 12, 14-31, 127)
    cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    cleaned = re.sub(r'\r\n|\r', '\n', cleaned)
    # Strip raw Docling scaffolding like [Section Context: ...]
    cleaned = re.sub(r'\[Section Context:[^\]]*\]', '', cleaned, flags=re.IGNORECASE)
    # Strip accidental inlined (Filename.pdf, Page X) or (Doc: ..., Page X) prose artifacts
    cleaned = re.sub(r'\s*\([^)]*?\.pdf,\s*(?:PDF\s*)?Page\s*\d+[^)]*?\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\[Doc:\s*[^\]]+?\.pdf,\s*(?:PDF\s*)?Page\s*\d+[^\]]*?\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\((?:p\.|page)\s*\d+\)', '', cleaned, flags=re.IGNORECASE)
    # Strip negative enumeration or omission explanations (e.g. "Excerpts [4] and [5] were omitted...")
    cleaned = re.sub(
        r'(?:(?:Excerpts?|Passages?|Sources?|References?)\s*(?:\[\d+\][,\s&and–-]*)+[^.\n]*(?:omitted|excluded|not\s+(?:used|relevant)|do\s+not\s+pertain|pertain\s+to|refer\s+to|irrelevant)[^.\n]*[.\n]?)',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )

        # Normalize colon followed immediately by text or newline

    cleaned = re.sub(r':\s*\n+', ':\n\n', cleaned)



    # Clean delimiter artifacts like ---:### or ---:#### or ---:

    cleaned = re.sub(r'^[ \t]*---:+\s*(#{1,4})\s*', r'\n\n\1 ', cleaned, flags=re.MULTILINE)

    cleaned = re.sub(r'^[ \t]*---:+\s*', r'\n\n---\n\n', cleaned, flags=re.MULTILINE)

    cleaned = re.sub(r'\n---:+#*', r'\n\n### ', cleaned)



    # Clean floating period on its own line (e.g. "alleles \n.")

    cleaned = re.sub(r'([A-Za-z0-9\)\"])[ \t]*\n+[ \t]*\.', r'\1.', cleaned)

    cleaned = re.sub(r'[ \t]*\n+[ \t]*\.', r'.', cleaned)

    cleaned = re.sub(r'\s+\.', '.', cleaned)



    # Clean Key:Value without space after colon (e.g. cultivars:Deciphered -> cultivars: Deciphered)

    cleaned = re.sub(r'([A-Za-z0-9\)])\:([A-Z])', r'\1: \2', cleaned)



    # Clean [Verified Knowledge Graph Facts] and other non-standard bracket tags

    cleaned = re.sub(r'\s*\[Verified Knowledge Graph[^\]]*\]', '', cleaned)

    cleaned = re.sub(r'\s*\[Knowledge Graph[^\]]*\]', '', cleaned)



    # Clean noisy OCR conference quotes like "inSTITUTE AFU L"

    cleaned = re.sub(r'\s*\(\s*e\.g\.,\s*["\']inSTITUTE AFU L["\']\s*\)', '', cleaned, flags=re.IGNORECASE)



    # Normalize standalone section markers like "A. Genome Analysis" into clean H4 markdown

    cleaned = re.sub(r'^[ \t]*([A-Z]\.\s+[A-Za-z0-9\s,–—\-]+)$', r'#### \1', cleaned, flags=re.MULTILINE)



    # Convert existing bullets to unicode bullet '• ' which triggers frontend rich card renderer

    cleaned = re.sub(r'(^|\n)\s*[\-\*\+]\s+', r'\1• ', cleaned)



    lines = [l.strip() for l in cleaned.split('\n')]
    processed = []
    i = 0
    in_entity_list = False
    entity_bullets = []

    under_intro = False
    while i < len(lines):
        line = lines[i]
        if not line:
            under_intro = False
            processed.append('')
            i += 1
            continue

        if line.startswith(('#', '---', '```', '>')):
            under_intro = False
            in_entity_list = False
            processed.append(line)
            i += 1
            continue

        if line.endswith(':') and not line.startswith(('•', '*', '-', '#')):
            under_intro = True
            in_entity_list = True
            processed.append(line)
            i += 1
            continue

        # Format "Key: Value" items into clean bullet points
        m_kv = re.match(r'^([A-Z][A-Za-z0-9\s/–—\-]+?):\s+([A-Z][\s\S]+)$', line)
        if m_kv and not line.startswith(('•', '*', '-', '#', '>')) and len(m_kv.group(1)) < 60:
            line = f"• **{m_kv.group(1)}**: {m_kv.group(2)}"
            under_intro = False
            in_entity_list = True
            processed.append(line)
            i += 1
            continue
        elif under_intro and not line.startswith(('•', '*', '-', '#', '>')) and len(line) > 10:
            line = f"• {line}"
            processed.append(line)
            i += 1
            continue

        # Check if line already has a bullet or number
        is_bullet = bool(re.match(r'^(?:•|\d+\.)\s+', line))

        # Check if previous line ended with a colon indicating an introductory list header
        prev_was_intro = bool(processed and any(processed[-j].endswith(':') for j in range(1, min(4, len(processed)+1)) if processed[-j]))

        # Detect standalone entity/name lines (do NOT match headings)
        is_entity_line = (
            not is_bullet and 
            not line.startswith('#') and
            (prev_was_intro or in_entity_list) and 
            len(line) < 80 and 
            (not line.endswith('.') or any(line.startswith(h) for h in ["Dr.", "Prof.", "Mr.", "Ms.", "Mrs.", "Shri", "Thiru."]))
        )

        if is_entity_line:
            raw_entity = line.strip('* ')
            line = f"• **{raw_entity}**"
            is_bullet = True
            in_entity_list = True
            entity_bullets.append(raw_entity)
        elif is_bullet:
            in_entity_list = True
        else:
            in_entity_list = False

        # Deduplicate consecutive identical lines or bullets (ignoring intermediate blank lines)
        last_non_empty = next((pl for pl in reversed(processed) if pl.strip()), None)
        if last_non_empty and line.strip() and line.strip() == last_non_empty.strip():
            i += 1
            continue
        processed.append(line)
        i += 1

    # Check if trailing paragraphs contain descriptive roles for the detected entity bullets
    if entity_bullets:
        final_lines = []
        for p_idx, pl in enumerate(processed):
            if any(pl == f"• **{ent}**" for ent in entity_bullets):
                ent_name = pl.replace("• **", "").replace("**", "").strip()
                core_name = re.sub(r"^(?:Dr\.|Prof\.|Thiru\.|Mr\.|Ms\.|Mrs\.|Shri)\s*", "", ent_name).split(",")[0].strip()
                matched_role = None
                for search_idx in range(len(processed)):
                    cand = processed[search_idx]
                    if cand and not cand.startswith("•") and core_name.lower() in cand.lower():
                        sents = re.split(r'(?<=[.!?])\s+', cand)
                        ent_sents = [s for s in sents if core_name.lower() in s.lower()]
                        if ent_sents:
                            matched_role = " ".join(ent_sents)
                            break
                if matched_role:
                    desc = re.sub(rf"^(?:.*?\b)?{re.escape(core_name)}\b(?:\s*,\s*IAS)?\s*(?:is\s+also|is\s+the|is)?\s*", "", matched_role, flags=re.IGNORECASE).strip()
                    desc = desc[0].upper() + desc[1:] if desc else matched_role
                    cits_in_role = re.findall(r"\[\d+\]", matched_role)
                    cit_str = f" {cits_in_role[0]}" if (cits_in_role and not re.search(r"\[\d+\]", desc)) else ""
                    final_lines.append(f"• **{ent_name}**: {desc}{cit_str}")
                else:
                    final_lines.append(pl)
            elif not pl.startswith("•") and any(re.sub(r"^(?:Dr\.|Prof\.|Thiru\.|Mr\.|Ms\.|Mrs\.|Shri)\s*", "", ent).split(",")[0].strip().lower() in pl.lower() for ent in entity_bullets):
                sents = re.split(r'(?<=[.!?])\s+', pl)
                remaining_sents = []
                for s in sents:
                    s_clean = re.sub(r"^(?:Dr\.|Prof\.|Thiru\.|Mr\.|Ms\.|Mrs\.|Shri|\s+|\[\d+\])+$", "", s).strip()
                    if s_clean and not any(re.sub(r"^(?:Dr\.|Prof\.|Thiru\.|Mr\.|Ms\.|Mrs\.|Shri)\s*", "", ent).split(",")[0].strip().lower() in s.lower() for ent in entity_bullets):
                        remaining_sents.append(s)
                if remaining_sents:
                    final_lines.append(" ".join(remaining_sents))
            else:
                final_lines.append(pl)
        processed = final_lines

    result = '\n'.join(processed)
    # Ensure double newlines around bullets
    result = re.sub(r'\n(•\s+)', r'\n\n\1', result)
    result = re.sub(r'(:\s*\n+)(•\s+)', r':\n\n\2', result)
    result = re.sub(r'\n{3,}', '\n\n', result)
    # Clean repetitive identical citations across bullet lists
    result = clean_repetitive_citations(result)
    return result.strip()


SYSTEM_SYNTHESIS_PROMPT = """You are an expert academic and institutional research intelligence assistant.
Answer the user's inquiry accurately, professionally, and concisely using ONLY the provided verified context chunks.

STRICT FORMATTING AND CITATION RULES:
1. CITATIONS & ANTI-REPETITION:
   - CRITICAL CITATION RULE: You MUST ground every factual claim, metric, or entity with an inline citation bracket referencing the source chunk index, e.g., "The institute established 4 new Centres of Excellence [1]."
   - Cite sources using simple numeric ASCII bracket markers ONLY: [1], [2], or multi-citation [1, 2].
   - NEVER cite '[Verified Knowledge Graph Facts]' or any non-numeric citation tag. Use ONLY numeric ASCII brackets: [1], [2].
   - Do NOT use bold unicode numbers (e.g. do NOT use [𝟏]). Use only standard ASCII brackets: [1], [2].
   - ANTI-REPETITION RULE: If an entire bullet list or series of points originates from the same source excerpt, cite the introductory statement or section header ONCE (e.g., "Key initiatives established [1]:"). Do NOT append identical citation tags (e.g., [1]) to every single bullet point in the list.
   - Attach citations to individual bullet points ONLY if different points cite different excerpts (e.g., Point A [1], Point B [2]).
   - NEVER write out the PDF filename, page number, or document title inside the answer text (e.g. NEVER write "(Report.pdf, Page 8) [1]" or "(Annual Report, p. 12)"). All document metadata will be rendered automatically by the UI via citation badges.
   - Do not add standalone citation summaries or bibliography blocks.

2. STRUCTURE & READABILITY:
   - CRITICAL SYNTAX RULE: NEVER output delimiter prefixes like '---:###' or '---:####' or '---:'. Headings MUST start strictly with markdown hashes e.g. '### Heading Name'. Never prepend dashes or colons to headings.
   - Always put a space after colons when introducing descriptions (e.g. '• **Topic**: Description', never 'Topic:Description').
   - NEVER leave a period on its own line. Concluding punctuation must directly follow the last word or citation.
   - Provide a natural, synthesized response. Do NOT simply dump raw context chunks.
   - Group related findings into clear thematic headings (### Heading) or formatted bullet points (`• `).
   - When listing persons, organizations, roles, recommendations, or key facts, ALWAYS format each entry as a bullet point starting with `• **Name/Title**: Description [citation]` on its own line.
   - ALWAYS leave a blank line before starting any list and after every bullet item.
   - Never output lists as unbulleted lines or inline comma-separated blocks.
   - If quoting an excerpt, present it as a clean blockquote (> "quote") or an indented excerpt.

3. DIRECT FACTUAL ANSWER:
   - State the direct, factual answer immediately in your first sentence.
   - If the user asks for a specific numeric metric, date, name, or total, provide that exact data upfront.

4. UNGROUNDED CLAIMS & STRICT BOUNDARIES:
   - Absolute negative constraint: NEVER extrapolate, speculate, or introduce external facts not present in the provided excerpts.
   - If the uploaded documents do not contain sufficient evidence to answer the query, state clearly what is missing rather than speculating.

5. NEGATIVE STATEMENTS & ABSENCE OF INFORMATION:
   - When stating that an event, entity, award, or fact is NOT mentioned, NOT won, or NOT present in the document (e.g. "did not win any Nobel Prizes", "no information is provided regarding..."), DO NOT attach any bracket citations [N].
   - Numeric bracket citations [1], [2] must ONLY be attached to sentences asserting positive facts directly quoted or extracted from the evidence.

6. RELEVANT PASSAGES & ANTI-ENUMERATION:
   - Only synthesize facts directly supported by the relevant context.
   - Do NOT enumerate, list, or explain why irrelevant passages or excerpts were omitted.
   - Use citations ([1], [2]) ONLY for the relevant excerpts that directly support your substantive claims.

7. TABULAR DATA & FINANCIAL COMPARISONS:
   - Institutional annual reports and academic documents frequently present longitudinal metrics in multi-column tables (e.g., statements organized by reporting periods like 'Current Year' and 'Previous Year').
   - In scanned OCR text, numbers and years may contain OCR noise: e.g., '31st March 2023' may appear in headers as 'Slst MARCH 2025' or 'Slst MARCH 2u2J', '53,55.00,000' as '53,55.00,Uuu', '48,50,00,000' as '48.S0_C)_(JL' or '48.50.0u.Uuu' (where 'S' is 5, representing 48,50,00,000 / 48.50 crore, NOT 48.80 crore). The source document metadata defines the true fiscal year. Extract figures from the relevant columns accordingly.
   - When asked to compare figures across years or calculate the difference/change, provide the reported figures for each year and accurately compute the arithmetic difference (Current Year minus Previous Year) without guessing.
   - Present the direct factual figures with bullet points and clear calculations. Do NOT append speculative meta-notes or trailing paragraphs discussing OCR transcription or artifact noise.

8. ENTITY BINDING & EXACT TERMINOLOGY INTEGRITY:
   - When answering about a specific named entity, gene, molecule, protein, investigator, organization, or metric:
     * Focus strictly and exclusively on the specific entity queried. Do NOT conflate traits, mechanisms, investigators, or outcomes from adjacent paragraphs or neighboring table rows.
     * Retain specific scientific, technical, numerical, and legal terminology verbatim from the text (including units, mutations, chemical formulas, dosages, identifiers, codes, and exact phrasing).
     * Report quantitative counts, statistics, and legal/patent statuses using the exact qualifying language stated in the verified source excerpts.

9. DETERMINISTIC STEP-BY-STEP ARITHMETIC:
   - When the user asks for differences, percentage changes, ratios, multiples, or combined totals:
     * Perform and show the exact step-by-step calculation using the verified figures extracted from the text:
       - Percentage change: ((New Value - Baseline Value) / Baseline Value) * 100%
       - Ratio / Multiple: Numerator / Denominator
       - Percentage of total: (Subset / Total) * 100%
       - Net Difference / Remainder: Total - Subsets
       - Combined Sum: Sum of all specified component metrics
     * State the exact resulting numerical value clearly in the answer.

10. DIRECT BREVITY & TOKEN CONCISENESS (HIGH TOKEN F1):
   - Never output generic introductory boilerplate such as "Based on the verified excerpts provided above...", "According to the uploaded documents...", or "Here is the information you requested:".
   - Start immediately with the direct, substantive answer in the very first sentence.
   - For multi-item queries (e.g., counts (a) through (i)), list each requested metric concisely on its own bullet point with its exact number.

11. FORMS, APPLICATION DOCUMENTS & INVERTED KEY-VALUE FIELDS:
   - In application forms, government certificates, examination forms, and OCR documents, field values frequently appear directly ABOVE the parenthesized label (e.g. 'SIDDHARTH TRIPATHI' directly above '(Full Name of the Applicant)').
   - When asked for a person's name, candidate name, or applicant name, extract and state the actual person's name ("Siddharth Tripathi") explicitly and upfront. Never state that the form merely "confirms the name" or treat the field as empty.
   - Accurately extract associated form fields (e.g., Enrollment ID, Date of Birth, Application Fee, Paper Code) directly alongside the name."""


def get_synthesis_system_prompt() -> str:
    """Returns the canonical system synthesis prompt string."""
    return SYSTEM_SYNTHESIS_PROMPT.strip()


def format_synthesis_user_prompt(query: str, evidence: str) -> str:
    """
    Constructs the formatted user prompt pairing the research query with retrieved evidence.
    """
    return f"""<user_query>
{query.strip()}
</user_query>

<retrieved_evidence>
{evidence.strip()}
</retrieved_evidence>

Please generate the grounded, cited answer following all system instructions:"""


def build_synthesis_chat_messages(
    query: str,
    evidence: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """
    Builds an OpenAI/vLLM compliant message list for multi-turn chat synthesis.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": get_synthesis_system_prompt()}
    ]

    # Append past conversation history if present
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content and role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

    # Append current turn with query and evidence
    user_content = format_synthesis_user_prompt(query, evidence)
    messages.append({"role": "user", "content": user_content})

    return messages