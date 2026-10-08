"""
RAISE Infrastructure — Neural Model Control Center (OLED Black Edition)
========================================================================
High-fidelity, ultra-low-overhead desktop mission control center for:
1. Dynamic Multi-Cloud Pipeline Phases (8-Phase Phase-to-Provider Assignment Matrix)
2. Per-LLM Real-time Token Usage & Cost Accounting (Prompt, Completion, Total, USD)
3. Underlying AI Model Subsystems & Health (FineCat-NLI, BGE-Large, BGE-Reranker, GGAHC, BM25)
4. Non-Destructive Hardware & Substrate Telemetry (CPU, RAM, GPU, Database Ports)
5. Masked Windows Credential Locker (DPAPI & .env management)

Architecture:
  - `src.gui.palette`: Palette constants, OLED pitch-black and pure green colors.
  - `src.gui.telemetry_probes`: Dynamic hardware and AI pipeline sensor probes.
  - `src.gui.tabs`: Tab builders for Phase Matrix, Token Metering, Providers, Models, Credentials, and Hardware.
  - `src.gui.control_panel`: Main coordinator hosting `launch_model_control_center`.

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with complete separation of UI panels.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("raise.gui.control_center")

# Re-export palette constants for 100% backward compatibility
from src.gui.palette import (
    BG_BLACK,
    PANEL_BG,
    CARD_BG,
    CARD_HEADER,
    BORDER_COLOR,
    BORDER_GREEN,
    BORDER_ACCENT,
    TEXT_WHITE,
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_DIM,
    GREEN_BRIGHT,
    GREEN_EMERALD,
    GREEN_DARK,
    GREEN_BG_CHIP,
    ACCENT_CYAN,
    ACCENT_AMBER,
    ACCENT_RED,
    ACCENT_PURPLE,
)

# Re-export telemetry probes
from src.gui.telemetry_probes import (
    check_port,
    get_hardware_telemetry,
    get_system_health,
    get_pipeline_models_health,
)

# Tab builders
from src.gui.tabs import (
    build_phase_matrix_tab,
    build_token_metering_tab,
    build_providers_tab,
    build_models_tab,
    build_credentials_tab,
    build_hardware_tab,
)

__all__ = [
    "BG_BLACK",
    "PANEL_BG",
    "CARD_BG",
    "CARD_HEADER",
    "BORDER_COLOR",
    "BORDER_GREEN",
    "BORDER_ACCENT",
    "TEXT_WHITE",
    "TEXT_PRIMARY",
    "TEXT_MUTED",
    "TEXT_DIM",
    "GREEN_BRIGHT",
    "GREEN_EMERALD",
    "GREEN_DARK",
    "GREEN_BG_CHIP",
    "ACCENT_CYAN",
    "ACCENT_AMBER",
    "ACCENT_RED",
    "ACCENT_PURPLE",
    "check_port",
    "get_hardware_telemetry",
    "get_system_health",
    "get_pipeline_models_health",
    "launch_model_control_center",
    "launch_operator_gui",
]


def launch_model_control_center():
    """Launch the RAISE Neural Model Control Center with pure black OLED aesthetics and proper green indicators."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print("Error: tkinter is not installed in the current Python environment.")
        return

    from src.infrastructure.credentials.manager import get_credential_manager
    from src.infrastructure.providers.router import get_provider_router
    from src.infrastructure.providers.diagnostics import ProviderDiagnostics
    from src.infrastructure.providers.token_tracker import get_token_tracker

    cred_mgr = get_credential_manager()
    router = get_provider_router()
    tracker = get_token_tracker()

    root = tk.Tk()
    root.title("RAISE — Neural Model Control Center (Multi-Cloud Dispatch & Model Ops)")
    root.geometry("980x760")
    root.minsize(900, 640)
    root.configure(bg=BG_BLACK)

    # Configure styles for ultra-thin 1px border lines and pitch black styling
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG_BLACK, foreground=TEXT_PRIMARY, font=("Segoe UI", 10), borderwidth=0)
    style.configure("TFrame", background=BG_BLACK)
    style.configure("Card.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
    style.configure("TLabel", background=BG_BLACK, foreground=TEXT_PRIMARY)
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY)

    # Notebook Tabs
    style.configure("TNotebook", background=BG_BLACK, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=CARD_HEADER,
        foreground=TEXT_MUTED,
        padding=[14, 8],
        font=("Segoe UI", 9, "bold"),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", "#14291f"), ("active", "#18181b")],
        foreground=[("selected", GREEN_BRIGHT), ("active", TEXT_WHITE)],
    )

    style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT_PRIMARY, rowheight=26, font=("Segoe UI", 9), borderwidth=1, relief="solid")
    style.configure("Treeview.Heading", background=CARD_HEADER, foreground=TEXT_WHITE, font=("Segoe UI", 9, "bold"), relief="flat", padding=[6, 4])
    style.map("Treeview", background=[("selected", "#064e3b")], foreground=[("selected", GREEN_BRIGHT)])

    # Top Header Banner
    header_frame = tk.Frame(root, bg=BG_BLACK, highlightthickness=1, highlightbackground=BORDER_GREEN)
    header_frame.pack(fill="x", padx=14, pady=(12, 6))

    top_title_box = tk.Frame(header_frame, bg=BG_BLACK)
    top_title_box.pack(side="left", padx=14, pady=10)
    
    title_row = tk.Frame(top_title_box, bg=BG_BLACK)
    title_row.pack(anchor="w")
    tk.Label(title_row, text="●", font=("Segoe UI", 12, "bold"), bg=BG_BLACK, fg=GREEN_BRIGHT).pack(side="left", padx=(0, 6))
    tk.Label(title_row, text="RAISE NEURAL MODEL CONTROL CENTER", font=("Segoe UI", 14, "bold"), bg=BG_BLACK, fg=TEXT_WHITE).pack(side="left")

    tk.Label(
        top_title_box,
        text="Mission Control: Multi-Cloud Dispatch Matrix | Live Token Metering (Per LLM) | Subsystem Health Observability",
        font=("Segoe UI", 9),
        bg=BG_BLACK,
        fg=TEXT_MUTED,
    ).pack(anchor="w", pady=(2, 0))

    top_badge_box = tk.Frame(header_frame, bg=BG_BLACK)
    top_badge_box.pack(side="right", padx=14, pady=10)

    mode_badge = tk.Label(
        top_badge_box,
        text=f"EXEC MODE: {router.mode.value}",
        font=("Segoe UI", 9, "bold"),
        bg=GREEN_BG_CHIP,
        fg=GREEN_BRIGHT,
        padx=10,
        pady=4,
        relief="solid",
        borderwidth=1,
        highlightbackground=GREEN_BRIGHT,
    )
    mode_badge.pack(side="right", padx=4)

    live_pulse = tk.Label(
        top_badge_box,
        text="ONLINE / HEALTHY",
        font=("Segoe UI", 9, "bold"),
        bg="#052e16",
        fg=GREEN_BRIGHT,
        padx=8,
        pady=4,
        relief="solid",
        borderwidth=1,
    )
    live_pulse.pack(side="right", padx=4)

    # Notebook Tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=14, pady=8)

    # Tab 1: Phase Matrix
    build_phase_matrix_tab(notebook=notebook, router=router)

    # Tab 2: Token Metering
    _, refresh_token_table = build_token_metering_tab(notebook=notebook, tracker=tracker)

    # Tab 3: Registered Providers
    _, refresh_llm_table = build_providers_tab(notebook=notebook, router=router, cred_mgr=cred_mgr, mode_badge=mode_badge)

    # Tab 4: Underlying AI Models
    _, refresh_models_table = build_models_tab(notebook=notebook)

    # Tab 5: Credential Locker
    (update_cred_status_display,) = build_credentials_tab(notebook=notebook, cred_mgr=cred_mgr, refresh_llm_callback=refresh_llm_table)

    # Tab 6: Hardware Telemetry
    _, refresh_hw_table = build_hardware_tab(notebook=notebook)

    # Bottom Actions Bar
    bottom_bar = tk.Frame(root, bg=BG_BLACK, highlightthickness=1, highlightbackground=BORDER_COLOR)
    bottom_bar.pack(fill="x", padx=14, pady=(6, 12))

    status_footer = tk.Label(bottom_bar, text="Ready — Multi-Cloud Pipeline & Model Control Center Active.", font=("Segoe UI", 9, "italic"), bg=BG_BLACK, fg=GREEN_BRIGHT)
    status_footer.pack(side="left", padx=12, pady=8)

    def run_diagnostics_modal():
        status_footer.config(text="Probing all cloud endpoints and micro-token latency...")
        root.update_idletasks()
        diag = ProviderDiagnostics()
        res = diag.run_all(timeout=12.0)
        table_txt = diag.format_table(res)
        status_footer.config(text="Health check completed.")

        win = tk.Toplevel(root)
        win.title("RAISE — Live Diagnostics Scorecard")
        win.geometry("760x380")
        win.configure(bg=BG_BLACK)
        txt = tk.Text(win, bg=BG_BLACK, fg=GREEN_BRIGHT, font=("Consolas", 10), padx=12, pady=12, relief="solid", borderwidth=1)
        txt.insert("1.0", table_txt)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh_all():
        refresh_token_table()
        refresh_llm_table()
        refresh_models_table()
        refresh_hw_table()
        update_cred_status_display()
        status_footer.config(text="Refreshed all metrics, token tallies, and provider states.")

    tk.Button(bottom_bar, text="🔄 Refresh All", command=refresh_all, bg="#052e16", fg=GREEN_BRIGHT, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=4).pack(side="right", padx=6)
    tk.Button(bottom_bar, text="🩺 Run Diagnostics", command=run_diagnostics_modal, bg=CARD_HEADER, fg=ACCENT_CYAN, font=("Segoe UI", 9, "bold"), relief="solid", borderwidth=1, padx=12, pady=4).pack(side="right", padx=6)
    tk.Button(bottom_bar, text="Exit", command=root.destroy, bg=CARD_HEADER, fg=TEXT_MUTED, font=("Segoe UI", 9), relief="solid", borderwidth=1, padx=10, pady=4).pack(side="right", padx=6)

    root.mainloop()


# Backwards compatibility alias
launch_operator_gui = launch_model_control_center

if __name__ == "__main__":
    launch_model_control_center()
