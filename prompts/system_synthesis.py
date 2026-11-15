"""
RAISE Academic GraphRAG Studio - System Synthesis Prompt Module
Formatted for optimal LLM adherence (Qwen 2.5, GPT-4, Claude, LLaMA)
with clear semantic boundaries, citation formatting, and anti-hallucination guardrails.
"""

import re
from typing import Dict, List, Optional


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

                    has_intro = prev_idx >= 0 and lines[prev_idx].strip().endswith(":")

                    if has_intro:
                        intro_line = lines[prev_idx]
                        if common_cit in intro_line:
                            for b_idx in bullet_indices:
                                lines[b_idx] = re.sub(
                                    rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx]
                                )
                        else:
                            colon_idx = intro_line.rfind(":")
                            lines[prev_idx] = f"{intro_line[:colon_idx].rstrip()} {common_cit}:"
                            for b_idx in bullet_indices:
                                lines[b_idx] = re.sub(
                                    rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx]
                                )
                    else:
                        first_kept = False
                        for b_idx in bullet_indices:
                            if common_cit in lines[b_idx]:
                                if not first_kept:
                                    first_kept = True
                                else:
                                    lines[b_idx] = re.sub(
                                        rf"\s*{re.escape(common_cit)}\s*(\.?)\s*$", r"\1", lines[b_idx]
                                    )
            continue
        i += 1

    return "\n".join(lines)


def sanitize_rag_text(text: str) -> str:
    """
    Sanitizes RAG text, stripping control characters, normalizing newlines,
    and ensuring bullet points, lists, and paragraphs are formatted cleanly for
    both terminal and web frontends without mutating grounded prose.
    """
    if not text:
        return ""

    # Strip non-printable control characters (ASCII 0-8, 11, 12, 14-31, 127)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    cleaned = re.sub(r"\r\n|\r", "\n", cleaned)

    # Strip internal scaffolding tags and leaked inline filename/page references
    cleaned = re.sub(
        r"\[(?:Section Context|Verified Knowledge Graph|Knowledge Graph)[^\]]*\]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*\([^)]*?\.pdf,\s*(?:PDF\s*)?Page\s*\d+[^)]*?\)", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\s*\[Doc:\s*[^\]]+?\.pdf,\s*(?:PDF\s*)?Page\s*\d+[^\]]*?\]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*\((?:p\.|page)\s*\d+\)", "", cleaned, flags=re.IGNORECASE)

    # Strip negative enumeration or omission explanations
    cleaned = re.sub(
        r"(?:(?:Excerpts?|Passages?|Sources?|References?)\s*(?:\[\d+\][,\s&and–-]*)+[^.\n]*(?:omitted|excluded|not\s+(?:used|relevant)|do\s+not\s+pertain|pertain\s+to|refer\s+to|irrelevant)[^.\n]*[.\n]?)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Normalize colon followed immediately by newline
    cleaned = re.sub(r":\s*\n+", ":\n\n", cleaned)

    # Clean delimiter artifacts like ---:### or ---:#### or ---:
    cleaned = re.sub(r"^[ \t]*---:+\s*(#{1,4})\s*", r"\n\n\1 ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[ \t]*---:+\s*", r"\n\n---\n\n", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n---:+#*", r"\n\n### ", cleaned)

    # Clean floating period on its own line
    cleaned = re.sub(r"([A-Za-z0-9\)\"])[ \t]*\n+[ \t]*\.", r"\1.", cleaned)
    cleaned = re.sub(r"[ \t]*\n+[ \t]*\.", r".", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)

    # Ensure space after colon in Key:Value pairs (ignoring URLs/timestamps)
    cleaned = re.sub(r"([A-Za-z\)])\:([A-Z])", r"\1: \2", cleaned)

    # Normalize standalone section markers like "A. Section Title" into H4 markdown
    cleaned = re.sub(
        r"^[ \t]*([A-Z]\.\s+[A-Za-z0-9\s,–—\-]+)$", r"#### \1", cleaned, flags=re.MULTILINE
    )

    # Convert standard markdown bullets to unicode bullet '• ' for frontend rich card renderer
    cleaned = re.sub(r"(^|\n)\s*[\-\*\+]\s+", r"\1• ", cleaned)

    # Deduplicate consecutive identical non-empty lines and format standalone Key: Value lines
    lines = [l.strip() for l in cleaned.split("\n")]
    processed: List[str] = []

    for line in lines:
        if not line:
            processed.append("")
            continue

        # Format unbulleted "Key: Value" lines into clean bullets (skipping headings/quotes)
        m_kv = re.match(r"^([A-Z][A-Za-z0-9\s/–—\-]{1,55}?):\s+([A-Z0-9₹$€£~][\s\S]+)$", line)
        if m_kv and not line.startswith(("•", "*", "-", "#", ">", "http")):
            line = f"• **{m_kv.group(1)}**: {m_kv.group(2)}"

        last_non_empty = next((pl for pl in reversed(processed) if pl.strip()), None)
        if last_non_empty and line == last_non_empty:
            continue

        processed.append(line)

    result = "\n".join(processed)
    # Ensure double newlines around bullets for frontend card rendering
    result = re.sub(r"\n(•\s+)", r"\n\n\1", result)
    result = re.sub(r"(:\s*\n+)(•\s+)", r":\n\n\2", result)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return clean_repetitive_citations(result).strip()


SYSTEM_SYNTHESIS_PROMPT = """You are an expert academic and institutional research intelligence assistant.
Answer the user's inquiry accurately, professionally, and concisely using ONLY the provided verified context chunks.

STRICT FORMATTING AND CITATION RULES:
1. CITATIONS & ANTI-REPETITION:
   - CRITICAL CITATION RULE: Ground every positive factual claim, metric, or entity with an inline citation bracket referencing the source chunk index, e.g., "The institute established 4 new Centres of Excellence [1]."
   - Use standard ASCII numeric brackets ONLY: [1], [2], or [1, 2]. Never use bold unicode brackets or non-numeric tags like '[Verified Knowledge Graph Facts]'.
   - ANTI-REPETITION RULE: If an entire bullet list originates from the same source excerpt, cite the introductory header ONCE (e.g., "Key initiatives established [1]:") and omit repetitive citation tags on individual child bullets.
   - Attach citations to individual bullet points ONLY when different bullets cite different source excerpts (e.g., Point A [1], Point B [2]).
   - NEVER write out PDF filenames, page numbers, or document titles in the answer prose. Do not append bibliography blocks.

2. STRUCTURE & READABILITY:
   - Headings MUST start strictly with markdown hashes (e.g., '### Heading Name'). Never prepend dashes or colons (such as '---:###') to headings.
   - Always place a space after colons when introducing descriptions (e.g., '• **Topic**: Description').
   - Group related findings under clear thematic headings (`### Heading`) or bullet points (`• `).
   - When listing entities, roles, metrics, or key facts, format each entry on its own line as `• **Name/Category**: Description [citation]` with a blank line between items.
   - Match the structure of your response directly to the query intent. Do not output boilerplate sections unrelated to the user's question.

3. DIRECT FACTUAL ANSWER & BREVITY:
   - State the direct, factual answer immediately in your very first sentence without introductory filler (never start with "Based on the provided excerpts..." or "According to the documents...").
   - If the query asks for a specific metric, name, date, contact detail, or count, provide that exact value upfront.

4. STRICT GROUNDING & NEGATIVE STATEMENTS:
   - NEVER extrapolate, speculate, or introduce external facts not present in the provided excerpts.
   - Before concluding information is absent, scan ALL provided excerpts [1] through [N].
   - When stating that an entity, metric, or event is NOT mentioned in the excerpts, DO NOT attach any citation brackets [N]. Only cite positive facts present in the text.
   - Do NOT explain or enumerate why irrelevant excerpts were omitted.

5. ENTITY BINDING & TERMINOLOGY INTEGRITY:
   - Focus strictly on the specific entity, gene, protein, investigator, committee, or metric queried. Do NOT conflate attributes or counts from adjacent paragraphs, unrelated appendices, or neighboring table rows.
   - Preserve scientific, technical, financial, and legal terminology, units, identifiers, and qualifying language verbatim from the source text.
   - For personal profiles, CVs, or resumes, extract complete verified contact details (emails, phone numbers with country codes, portfolio/GitHub/LinkedIn links), education, and experience accurately.

6. TABULAR DATA, OCR RESILIENCE & ARITHMETIC:
   - Multi-column institutional and financial tables often compare reporting periods (e.g., Current Year vs. Previous Year). Use document metadata and column headers to map values to the correct fiscal year.
   - Scanned OCR tables may contain character substitutions inside numbers or dates (such as 'S' for '5', 'O'/'u'/'U' for '0', 'l'/'I' for '1', or 'J' for '3'). Resolve corrupted digits using column alignment, unit labels (e.g., Lakhs/Crores), and row subtotals without adding meta-commentary about OCR noise.
   - When asked for differences, percentage changes, ratios, or totals, show the explicit step-by-step calculation using the extracted figures:
     * Difference: Current Period Value - Previous Period Value
     * Percentage Change: ((New Value - Baseline Value) / Baseline Value) * 100%
     * Share of Total: (Subset / Total) * 100%

7. TABLE ALIGNMENT, NULL SYMBOLS & SUMMARY COUNTS VS. ROSTERS:
   - In tables and schedules, symbols such as '~', '-', 'Nil', 'N/A', or blank cells indicate zero or not applicable.
   - Maintain strict 1-to-1 horizontal and vertical alignment between column/row headers and cell values. Never skip a '~' or '-' symbol or shift subsequent numbers into preceding categories.
     * Example: For headers [Category A, Category B, Category C] and row values [76, ~, 279], report Category A: 76, Category B: ~ (Nil / Not Applicable), Category C: 279.
   - When a query asks for quantitative statistics (e.g., "Number of..."), report the numerical breakdown and totals from the summary statistics table rather than listing individual names from a roster.
   - Conversely, when a query asks for members of a specific governance body or nominee category (e.g., Senate nominees on a Board), extract only the individuals listed under that exact heading rather than general institution-wide rosters.

8. FORMS & INVERTED KEY-VALUE FIELDS:
   - In scanned application forms, certificates, and official receipts, field values frequently appear on the line directly ABOVE their parenthesized field label (e.g., `<Applicant Name>` printed directly above `(Full Name of the Applicant)`).
   - Extract and state the actual filled value upfront along with any requested companion fields (such as Enrollment/Application ID, Date of Birth, Fee, or Paper Code)."""


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

    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content and role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

    user_content = format_synthesis_user_prompt(query, evidence)
    messages.append({"role": "user", "content": user_content})

    return messages
