"""
RAISE TUI — Developer Dark Theme & Layout CSS
==============================================
Dark developer styling matching connector/helper.ps1 with TrueColor accents.
"""

from __future__ import annotations

# Monochrome & TrueColor palette constants
CLR_BG_BASE = "#121212"
CLR_BG_SURFACE = "#181818"
CLR_BG_PANEL = "#1e1e1e"
CLR_BORDER = "#3a3a3a"
CLR_BORDER_FOCUSED = "#5fd7ff"

CLR_CYAN = "#5fd7ff"
CLR_GREEN = "#87d787"
CLR_YELLOW = "#ffd75f"
CLR_RED = "#ff5f5f"
CLR_PURPLE = "#af87ff"
CLR_WHITE = "#eeeeee"
CLR_DIM = "#767676"

TUI_CSS = """
Screen {
    background: #121212;
    color: #eeeeee;
    layout: vertical;
    overflow: hidden;
}

#top-header {
    dock: top;
    height: 3;
    background: #181818;
    border-bottom: heavy #3a3a3a;
    padding: 0 1;
}

#header-title {
    color: #5fd7ff;
    text-style: bold;
}

#header-stats {
    color: #ffd75f;
    text-align: right;
}

#main-container {
    height: 1fr;
    layout: horizontal;
}

#tabbed-content {
    width: 1fr;
    height: 100%;
}

#right-inspector {
    width: 48;
    height: 100%;
    background: #181818;
    border-left: heavy #3a3a3a;
    padding: 0 1;
    display: block;
}

#right-inspector.hidden {
    display: none;
}

#inspector-title {
    color: #af87ff;
    text-style: bold;
    border-bottom: solid #3a3a3a;
    margin-bottom: 1;
}

#bottom-dock {
    dock: bottom;
    height: 5;
    background: #181818;
    border-top: heavy #3a3a3a;
    padding: 0 1;
}

#composer-container {
    height: 3;
    layout: horizontal;
}

#mode-pill {
    width: 11;
    height: 3;
    color: #121212;
    background: #5fd7ff;
    text-style: bold;
    content-align: center middle;
    margin-right: 1;
}

#mode-pill.mode-insert {
    background: #87d787;
    color: #121212;
}

#mode-pill.mode-command {
    background: #ffd75f;
    color: #121212;
}

#mode-pill.mode-search {
    background: #af87ff;
    color: #121212;
}

#composer-input {
    width: 1fr;
    height: 3;
    background: #1e1e1e;
    color: #eeeeee;
    border: none;
}

#composer-input:focus {
    border: tall #5fd7ff;
}

#shortcut-bar {
    height: 1;
    color: #767676;
    background: #181818;
    padding-left: 1;
}

/* Tab contents */
.tab-pane {
    height: 100%;
    padding: 0 1;
}

.log-scroll {
    height: 100%;
    background: #121212;
}

/* Boot Tab */
#boot-list {
    height: 1fr;
}

/* Data Flow Waterfall */
#flow-list {
    height: 1fr;
}

/* Search bar overlay */
#search-bar {
    dock: top;
    height: 3;
    background: #1e1e1e;
    border-bottom: solid #af87ff;
    display: none;
    padding: 0 1;
}

#search-bar.visible {
    display: block;
}
"""
