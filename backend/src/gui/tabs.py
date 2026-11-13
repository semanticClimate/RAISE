"""
RAISE GUI Control Center Tab Builders
======================================
Purpose:
  Provides modular tab builder functions for the RAISE Neural Model Control Center:
  1. `build_phase_matrix_tab`: Dynamic Multi-Cloud Pipeline Phases.
  2. `build_token_metering_tab`: Per-LLM Real-Time Token Breakdown & Billable Metering.
  3. `build_providers_tab`: Registered LLM Providers & Cost Modes.
  4. `build_models_tab`: Underlying Non-LLM Models & Subsystem Health.
  5. `build_credentials_tab`: Masked DPAPI Windows Credential Locker.
  6. `build_hardware_tab`: Non-destructive host hardware sensors.

Author: RAISE Core Architecture Team
Maintainability: Keep under 380 lines with clean tkinter UI construction.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Tuple

from src.gui.palette import (
    BG_BLACK,
    CARD_BG,
    CARD_HEADER,
    BORDER_COLOR,
    BORDER_GREEN,
    TEXT_WHITE,
    TEXT_PRIMARY,
    TEXT_MUTED,
    GREEN_BRIGHT,
    GREEN_BG_CHIP,
    ACCENT_CYAN,
    ACCENT_RED,
)
from src.gui.telemetry_probes import (
    get_hardware_telemetry,
    get_pipeline_models_health,
)
from src.core.config import models


def build_phase_matrix_tab(notebook: ttk.Notebook, router: Any) -> None:
    """Builds Tab 1: Pipeline Phase Matrix (8-Phase Assignment Matrix)."""
    from src.infrastructure.providers.router import InferenceTask

    tab_phases = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_phases, text=" 🔀  Pipeline Phase Matrix ")

    phase_info_box = tk.Frame(tab_phases, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER_COLOR)
    phase_info_box.pack(fill="x", padx=10, pady=8)
    
    p_info_header = tk.Frame(phase_info_box, bg=CARD_BG)
    p_info_header.pack(anchor="w", padx=10, pady=(6, 2))
    tk.Label(p_info_header, text="●", font=("Segoe UI", 10), bg=CARD_BG, fg=GREEN_BRIGHT).pack(side="left", padx=(0, 6))
    tk.Label(p_info_header, text="Dynamic Multi-Cloud Pipeline Phases", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT).pack(side="left")

    tk.Label(
        phase_info_box,
        text="RAISE dispatches dedicated cloud LLMs tailored for distinct functional phases (e.g. Groq for sub-350ms user chat and query reformulation, "
             "Gemini for PDF vision/tables, DeepSeek for multi-hop graph reasoning, OpenRouter / NVIDIA NIM for generation, Cohere for neural cross-reranking).",
        font=("Segoe UI", 9),
        bg=CARD_BG,
        fg=TEXT_MUTED,
        wraplength=900,
        justify="left",
    ).pack(anchor="w", padx=10, pady=(0, 6))

    tasks_grid_frame = tk.LabelFrame(
        tab_phases,
        text=" Phase-to-Provider Assignment Matrix (8 Real-Time Workflows) ",
        font=("Segoe UI", 9, "bold"),
        bg=CARD_BG,
        fg=GREEN_BRIGHT,
        highlightthickness=1,
        highlightbackground=BORDER_COLOR,
        bd=0,
        padx=12,
        pady=8,
    )
    tasks_grid_frame.pack(fill="both", expand=True, padx=10, pady=6)

    header_cols = [("Phase & Pipeline Responsibility", 380), ("Assigned Cloud LLM", 140), ("Target Model Override", 200), ("Routing Status", 130)]
    for ci, (col_name, _) in enumerate(header_cols):
        h_lbl = tk.Label(tasks_grid_frame, text=col_name, font=("Segoe UI", 9, "bold"), bg=CARD_HEADER, fg=TEXT_WHITE, padx=6, pady=4, relief="solid", borderwidth=1)
        h_lbl.grid(row=0, column=ci, sticky="ew", padx=2, pady=(0, 6))

    task_combos: Dict[Any, ttk.Combobox] = {}
    task_model_entries: Dict[Any, tk.Entry] = {}
    provider_options = ["groq", "gemini", "openrouter", "nvidia", "deepseek", "cohere", "vllm"]

    pipeline_phases_matrix = [
        (InferenceTask.CHAT, "Phase 1: Interactive User Chat (Low-latency conversation)", "groq", models.GROQ_MODEL_NAME),
        (InferenceTask.RAG_GENERATION, "Phase 2: RAG Answer Synthesis (Full grounded response generation)", "openrouter", models.OPENAI_MODEL_NAME),
        (InferenceTask.DOCUMENT_EXTRACTION, "Phase 3: Document Layout & Vision (Tables, PDF coordinate spans)", "gemini", models.GEMINI_MODEL_NAME),
        (InferenceTask.QUERY_REWRITE, "Phase 4: Query Intake & Reformulation (Coreference & decomposition)", "groq", models.GROQ_MODEL_NAME),
        (InferenceTask.REASONING, "Phase 5: Multi-Hop Relational Reasoning (Logic & Cypher Path Critic)", "deepseek", models.DEEPSEEK_MODEL_NAME),
        (InferenceTask.CODE, "Phase 6: Code & Formal Cypher Generation (AST & Graph queries)", "deepseek", models.DEEPSEEK_MODEL_NAME),
        (InferenceTask.SUMMARIZATION, "Phase 7: Community / Executive Summaries (High-level abstractive)", "openrouter", models.OPENROUTER_MODEL_NAME),
        (InferenceTask.RERANKING, "Phase 8: Passage Relevance Scoring (Cross-attention neural reranking)", "cohere", "rerank-v3.5"),
    ]

    for row_idx, (task_enum, desc, default_prov, default_mod) in enumerate(pipeline_phases_matrix, start=1):
        curr_provider = router.task_policy.get(task_enum, default_prov)

        lbl_p = tk.Label(tasks_grid_frame, text=desc, font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_PRIMARY, anchor="w")
        lbl_p.grid(row=row_idx, column=0, sticky="w", padx=6, pady=4)

        combo = ttk.Combobox(tasks_grid_frame, values=provider_options, state="readonly", width=14)
        combo.set(curr_provider)
        combo.grid(row=row_idx, column=1, sticky="w", padx=4, pady=4)
        task_combos[task_enum] = combo

        mod_entry = tk.Entry(tasks_grid_frame, bg="#141418", fg=GREEN_BRIGHT, insertbackground=GREEN_BRIGHT, font=("Consolas", 9), width=24, relief="solid", borderwidth=1)
        mod_entry.insert(0, default_mod)
        mod_entry.grid(row=row_idx, column=2, sticky="w", padx=4, pady=4)
        task_model_entries[task_enum] = mod_entry

        st_tag = tk.Label(tasks_grid_frame, text="● READY", font=("Segoe UI", 8, "bold"), bg=GREEN_BG_CHIP, fg=GREEN_BRIGHT, padx=8, pady=2, relief="solid", borderwidth=1)
        st_tag.grid(row=row_idx, column=3, sticky="w", padx=6, pady=4)

    def save_phase_policies():
        for t, combo in task_combos.items():
            chosen_prov = combo.get()
            router.set_task_provider(t, chosen_prov)
            m_override = task_model_entries[t].get().strip()
            if m_override and chosen_prov in router.providers:
                setattr(router.providers[chosen_prov], "model_name", m_override)
        messagebox.showinfo("Matrix Saved", "Dynamic Multi-Cloud Phase Assignment Matrix successfully bound to runtime!")

    btn_row_phase = tk.Frame(tab_phases, bg=BG_BLACK)
    btn_row_phase.pack(fill="x", padx=10, pady=(2, 8))
    
    apply_btn = tk.Button(
        btn_row_phase,
        text="💾 Apply & Save Multi-Cloud Phase Matrix",
        command=save_phase_policies,
        bg="#052e16",
        fg=GREEN_BRIGHT,
        font=("Segoe UI", 9, "bold"),
        relief="solid",
        borderwidth=1,
        padx=16,
        pady=6,
    )
    apply_btn.pack(side="left", padx=4)


def build_token_metering_tab(notebook: ttk.Notebook, tracker: Any) -> Tuple[ttk.Treeview, Callable[[], None]]:
    """Builds Tab 2: Token Usage & Cost Accounting (Per LLM)."""
    tab_tokens = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_tokens, text=" 📊  Token Metering (Per LLM) ")

    kpi_frame = tk.Frame(tab_tokens, bg=BG_BLACK)
    kpi_frame.pack(fill="x", padx=10, pady=8)

    def make_kpi(parent, title, val, color=GREEN_BRIGHT):
        box = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER_GREEN, padx=14, pady=10)
        box.pack(side="left", expand=True, fill="both", padx=6)
        tk.Label(box, text=title, font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=TEXT_MUTED).pack(anchor="w")
        lbl_val = tk.Label(box, text=val, font=("Segoe UI", 16, "bold"), bg=CARD_BG, fg=color)
        lbl_val.pack(anchor="w", pady=(2, 0))
        return lbl_val

    kpi_tokens_lbl = make_kpi(kpi_frame, "TOTAL TOKENS CONSUMED", "0", GREEN_BRIGHT)
    kpi_calls_lbl = make_kpi(kpi_frame, "ACTIVE INFERENCE INVOCATIONS", "0", TEXT_WHITE)
    kpi_cost_lbl = make_kpi(kpi_frame, "ESTIMATED MULTI-CLOUD COST", "$0.0000", ACCENT_CYAN)

    token_box = tk.LabelFrame(
        tab_tokens,
        text=" Per-LLM Real-Time Token Breakdown & Billable Metering ",
        font=("Segoe UI", 9, "bold"),
        bg=CARD_BG,
        fg=GREEN_BRIGHT,
        highlightthickness=1,
        highlightbackground=BORDER_COLOR,
        bd=0,
        padx=10,
        pady=8,
    )
    token_box.pack(fill="both", expand=True, padx=10, pady=6)

    tok_cols = ("provider", "model", "prompt", "completion", "total", "requests", "cost", "last_active")
    tok_tree = ttk.Treeview(token_box, columns=tok_cols, show="headings", height=8)
    tok_tree.heading("provider", text="LLM Provider")
    tok_tree.heading("model", text="Active Model")
    tok_tree.heading("prompt", text="Prompt Tokens")
    tok_tree.heading("completion", text="Completion Tokens")
    tok_tree.heading("total", text="Total Tokens")
    tok_tree.heading("requests", text="Invocations")
    tok_tree.heading("cost", text="Est. Cost (USD)")
    tok_tree.heading("last_active", text="Last Active")

    tok_tree.column("provider", width=120)
    tok_tree.column("model", width=190)
    tok_tree.column("prompt", width=100)
    tok_tree.column("completion", width=120)
    tok_tree.column("total", width=100)
    tok_tree.column("requests", width=90)
    tok_tree.column("cost", width=100)
    tok_tree.column("last_active", width=140)
    tok_tree.pack(fill="both", expand=True)

    def refresh_token_table():
        tok_tree.delete(*tok_tree.get_children())
        stats = tracker.get_all_stats()
        totals = tracker.get_aggregate_totals()

        kpi_tokens_lbl.config(text=f"{totals['total_tokens']:,}")
        kpi_calls_lbl.config(text=f"{totals['total_requests']:,}")
        kpi_cost_lbl.config(text=f"${totals['total_cost_usd']:.4f}")

        for p_name, data in stats.items():
            tok_tree.insert(
                "",
                "end",
                values=(
                    p_name.upper(),
                    data.get("active_model", "default"),
                    f"{data.get('prompt_tokens', 0):,}",
                    f"{data.get('completion_tokens', 0):,}",
                    f"{data.get('total_tokens', 0):,}",
                    f"{data.get('requests_count', 0):,}",
                    f"${data.get('estimated_cost_usd', 0.0):.5f}",
                    data.get("last_active", "Idle"),
                ),
            )

    tok_btn_bar = tk.Frame(tab_tokens, bg=BG_BLACK)
    tok_btn_bar.pack(fill="x", padx=10, pady=(2, 8))

    def reset_tokens_action():
        if messagebox.askyesno("Reset Token Metering", "Reset session token counters for all LLMs to zero?"):
            tracker.reset_counters()
            refresh_token_table()

    tk.Button(tok_btn_bar, text="🔄 Refresh Token Counters", command=refresh_token_table, bg="#052e16", fg=GREEN_BRIGHT, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=5).pack(side="left", padx=4)
    tk.Button(tok_btn_bar, text="🗑️ Reset Session Counters", command=reset_tokens_action, bg=CARD_HEADER, fg=ACCENT_RED, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=5).pack(side="left", padx=4)

    return tok_tree, refresh_token_table


def build_providers_tab(notebook: ttk.Notebook, router: Any, cred_mgr: Any, mode_badge: tk.Label) -> Tuple[ttk.Treeview, Callable[[], None]]:
    """Builds Tab 3: Registered LLM Providers & Execution Modes."""
    tab_runtime = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_runtime, text=" ⚡  Registered Providers ")

    mode_box = tk.LabelFrame(tab_runtime, text=" Global Execution Mode ", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT, highlightthickness=1, highlightbackground=BORDER_COLOR, bd=0, padx=12, pady=10)
    mode_box.pack(fill="x", padx=10, pady=8)

    mode_var = tk.StringVar(value=router.mode.value)

    def on_mode_change():
        selected = mode_var.get()
        router.set_execution_mode(selected)
        if selected == "CLOUD":
            router.set_cloud_allowed(True)
        mode_badge.config(text=f"EXEC MODE: {selected}")
        mode_status_lbl.config(text=f"Active Target: {selected}")

    modes = [("1. Local-First (vLLM)", "LOCAL"), ("2. Cloud Providers", "CLOUD"), ("3. Automatic Policy Routing", "AUTOMATIC")]
    for text, val in modes:
        r = tk.Radiobutton(mode_box, text=text, value=val, variable=mode_var, command=on_mode_change, bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=BG_BLACK, activebackground=CARD_BG, activeforeground=GREEN_BRIGHT, font=("Segoe UI", 9))
        r.pack(side="left", padx=14)

    mode_status_lbl = tk.Label(mode_box, text=f"Active Target: {router.mode.value}", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT)
    mode_status_lbl.pack(side="right", padx=10)

    llm_table_box = tk.LabelFrame(tab_runtime, text=" Registered LLM Providers & Cost Modes ", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT, highlightthickness=1, highlightbackground=BORDER_COLOR, bd=0, padx=10, pady=10)
    llm_table_box.pack(fill="both", expand=True, padx=10, pady=8)

    llm_cols = ("provider", "type", "cost_mode", "status", "source", "endpoint")
    llm_tree = ttk.Treeview(llm_table_box, columns=llm_cols, show="headings", height=8)
    llm_tree.heading("provider", text="Provider")
    llm_tree.heading("type", text="Type")
    llm_tree.heading("cost_mode", text="Cost Mode")
    llm_tree.heading("status", text="Credential Status")
    llm_tree.heading("source", text="Key Source")
    llm_tree.heading("endpoint", text="Default Endpoint")

    llm_tree.column("provider", width=120)
    llm_tree.column("type", width=70)
    llm_tree.column("cost_mode", width=190)
    llm_tree.column("status", width=120)
    llm_tree.column("source", width=110)
    llm_tree.column("endpoint", width=220)
    llm_tree.pack(fill="both", expand=True)

    def refresh_llm_table():
        llm_tree.delete(*llm_tree.get_children())
        cred_statuses = cred_mgr.list_all_statuses()
        providers_meta = [
            ("Local vLLM", "Local", "LOCAL / NO EXTERNAL API BILLING", "vllm", "http://localhost:8002/v1"),
            ("Groq", "Cloud", "CLOUD / USER ACCOUNT", "groq", "https://api.groq.com/openai/v1"),
            ("Google Gemini", "Cloud", "CLOUD / USER ACCOUNT", "gemini", "https://generativelanguage.googleapis.com"),
            ("OpenRouter", "Cloud", "CLOUD / USER ACCOUNT", "openrouter", "https://openrouter.ai/api/v1"),
            ("NVIDIA NIM", "Cloud", "CLOUD / USER ACCOUNT", "nvidia", "https://integrate.api.nvidia.com/v1"),
            ("Cohere", "Cloud", "CLOUD / USER ACCOUNT", "cohere", "https://api.cohere.com"),
            ("DeepSeek", "Cloud", "CLOUD / USER ACCOUNT", "deepseek", "https://api.deepseek.com"),
        ]
        for name, p_type, cost_mode, key, endpoint in providers_meta:
            info = cred_statuses.get(key, {"status": "missing", "source": "none"})
            st = "CONFIGURED" if (info["status"] == "configured" or key == "vllm") else "MISSING KEY"
            src = info["source"] if key != "vllm" else "Local Service"
            llm_tree.insert("", "end", values=(name, p_type, cost_mode, st, src, endpoint))

    return llm_tree, refresh_llm_table


def build_models_tab(notebook: ttk.Notebook) -> Tuple[ttk.Treeview, Callable[[], None]]:
    """Builds Tab 4: Underlying Non-LLM Models & Subsystem Health."""
    tab_models = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_models, text=" 🧠  Underlying AI Models ")

    models_box = tk.LabelFrame(tab_models, text=" Non-LLM Pipeline Models & Retrieval Infrastructure ", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT, highlightthickness=1, highlightbackground=BORDER_COLOR, bd=0, padx=10, pady=10)
    models_box.pack(fill="both", expand=True, padx=10, pady=8)

    mod_cols = ("subsystem", "model", "status", "details")
    mod_tree = ttk.Treeview(models_box, columns=mod_cols, show="headings", height=10)
    mod_tree.heading("subsystem", text="Subsystem / Layer")
    mod_tree.heading("model", text="Underlying Model / Component")
    mod_tree.heading("status", text="Health Status")
    mod_tree.heading("details", text="Technical Details & Metrics")

    mod_tree.column("subsystem", width=170)
    mod_tree.column("model", width=220)
    mod_tree.column("status", width=120)
    mod_tree.column("details", width=340)
    mod_tree.pack(fill="both", expand=True)

    def refresh_models_table():
        mod_tree.delete(*mod_tree.get_children())
        data = get_pipeline_models_health()
        for layer_name, info in data.items():
            mod_tree.insert("", "end", values=(layer_name, info["model"], info["status"], info["details"]))

    return mod_tree, refresh_models_table


def build_credentials_tab(notebook: ttk.Notebook, cred_mgr: Any, refresh_llm_callback: Callable[[], None]) -> Tuple[Callable[[], None]]:
    """Builds Tab 5: Masked Windows Credential Locker (DPAPI & .ENV)."""
    tab_creds = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_creds, text=" 🔐  Credential Locker ")

    cred_box = tk.LabelFrame(tab_creds, text=" Manage Cloud API Keys (Masked DPAPI Locker) ", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT, highlightthickness=1, highlightbackground=BORDER_COLOR, bd=0, padx=14, pady=14)
    cred_box.pack(fill="x", padx=10, pady=8)

    tk.Label(cred_box, text="Provider:", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=6)
    prov_select = ttk.Combobox(cred_box, values=["openrouter", "nvidia", "groq", "gemini", "deepseek", "cohere"], state="readonly", width=20)
    prov_select.set("openrouter")
    prov_select.grid(row=0, column=1, sticky="w", pady=6, padx=8)

    tk.Label(cred_box, text="API Key Secret:", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).grid(row=1, column=0, sticky="w", pady=6)
    key_entry = tk.Entry(cred_box, show="*", width=46, bg="#141418", fg=GREEN_BRIGHT, insertbackground=GREEN_BRIGHT, relief="solid", borderwidth=1)
    key_entry.grid(row=1, column=1, sticky="w", pady=6, padx=8)

    cred_status_lbl = tk.Label(cred_box, text="Status: Loading...", font=("Segoe UI", 9, "italic"), bg=CARD_BG, fg=GREEN_BRIGHT)
    cred_status_lbl.grid(row=2, column=1, sticky="w", pady=4, padx=8)

    def update_cred_status_display(*args):
        p = prov_select.get().strip()
        st = cred_mgr.get_credential_status(p).upper()
        src = cred_mgr.get_credential_source(p)
        cred_status_lbl.config(text=f"Status: {st} (Storage: {src})")

    prov_select.bind("<<ComboboxSelected>>", update_cred_status_display)

    cred_btn_row = tk.Frame(cred_box, bg=CARD_BG)
    cred_btn_row.grid(row=3, column=0, columnspan=2, pady=12)

    def save_cred_action():
        p = prov_select.get().strip()
        k = key_entry.get().strip()
        if not k:
            messagebox.showwarning("Input Error", "Please provide a non-empty API key.")
            return
        if cred_mgr.set_credential(p, k):
            key_entry.delete(0, tk.END)
            update_cred_status_display()
            refresh_llm_callback()
            messagebox.showinfo("Saved", f"API key for {p} saved safely into Windows Credential Locker.")
        else:
            messagebox.showerror("Error", f"Failed to save key for {p}.")

    def delete_cred_action():
        p = prov_select.get().strip()
        if messagebox.askyesno("Confirm Removal", f"Delete stored key for {p}?"):
            cred_mgr.delete_credential(p)
            update_cred_status_display()
            refresh_llm_callback()
            messagebox.showinfo("Removed", f"Credential for {p} cleared.")

    tk.Button(cred_btn_row, text="💾 Save to Locker", command=save_cred_action, bg="#052e16", fg=GREEN_BRIGHT, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=5).pack(side="left", padx=6)
    tk.Button(cred_btn_row, text="🗑️ Delete Key", command=delete_cred_action, bg=CARD_HEADER, fg=ACCENT_RED, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=5).pack(side="left", padx=6)

    return (update_cred_status_display,)


def build_hardware_tab(notebook: ttk.Notebook) -> Tuple[ttk.Treeview, Callable[[], None]]:
    """Builds Tab 6: Hardware & System Telemetry."""
    tab_hardware = tk.Frame(notebook, bg=BG_BLACK)
    notebook.add(tab_hardware, text=" ⚡  Hardware & Host ")

    hw_box = tk.LabelFrame(tab_hardware, text=" Live Dynamic Hardware Metrics (Zero Hardcoding) ", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=GREEN_BRIGHT, highlightthickness=1, highlightbackground=BORDER_COLOR, bd=0, padx=10, pady=10)
    hw_box.pack(fill="both", expand=True, padx=10, pady=8)

    hw_cols = ("resource", "status", "telemetry")
    hw_tree = ttk.Treeview(hw_box, columns=hw_cols, show="headings", height=8)
    hw_tree.heading("resource", text="System Resource")
    hw_tree.heading("status", text="Sensor Status")
    hw_tree.heading("telemetry", text="Measured Metric")
    hw_tree.column("resource", width=180)
    hw_tree.column("status", width=120)
    hw_tree.column("telemetry", width=480)
    hw_tree.pack(fill="both", expand=True)

    def refresh_hw_table():
        hw_tree.delete(*hw_tree.get_children())
        hw_data = get_hardware_telemetry()
        for res_name, info in hw_data.items():
            hw_tree.insert("", "end", values=(res_name, info["status"], info["details"]))

    return hw_tree, refresh_hw_table
