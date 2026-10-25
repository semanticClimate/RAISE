# 🛡️ Security Subsystem (`backend/src/security/`)

> **ASGI Security Shield, Ephemeral Token Handshake, Port Sweep & Edge Defense**

---

## 🌟 Overview

The `src/security/` package implements the zero-trust security perimeter and runtime stability safeguards for the RAISE backend. It isolates incoming HTTP/WebSocket traffic, blocks malicious IP addresses, manages tunnel watchdogs, and prevents memory exhaustion during large document uploads.

---

## 🔄 Security Shield & Request Inspection Flow

```mermaid
flowchart TD
    %% Inbound
    RawRequest(["🌐 Inbound HTTP / WebSocket Request"]):::inNode

    %% Security Subsystem
    subgraph SecuritySubsystem ["🛡️ src/security/ Defense Perimeter"]
        direction TB
        IPResolver["ip_resolver.py<br/>Extracts True Client IP from CF-Connecting-IP / X-Forwarded-For"]

        BlacklistCheck["O(1) Redis Blacklist Check<br/>(Immediate HTTP 403 on Banned IPs)"]

        subgraph ShieldEngine ["ASGI Shield & Guards (asgi_shield.py)"]
            direction LR
            Handshake["handshake_manager.py<br/>Two-Step Ephemeral Handshake Token Validation"]
            UploadGuard["Upload Memory Safeguard<br/>Bypasses Buffer Capture on Multipart Paths"]
            Handshake ~~~ UploadGuard
        end

        PortCleaner["port_sweep.py<br/>Pre-Flight Port 8000 Zombie Process Remediation"]
        Watchdog["process_watchdog.py<br/>Windows Job Object & Tunnel Subprocess Isolation"]
    end

    %% Internal Target
    FastAPIApp(["🚀 Sanitized Request Handed to FastAPI Routers"]):::outNode

    RawRequest --> IPResolver
    IPResolver --> BlacklistCheck
    BlacklistCheck -->|"Allowed"| ShieldEngine
    ShieldEngine --> FastAPIApp

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`asgi_shield.py`** | Pure ASGI middleware interceptor. Inspects inbound payloads, enforces origin filters, and protects memory from buffering large multi-megabyte PDF streams. |
| **`handshake_manager.py`** | Two-step WebSocket and SSE handshake manager with atomic key eviction, ensuring only authenticated UI sessions receive token streams. |
| **`ip_resolver.py`** | Safely extracts real client IP addresses across reverse proxies, Cloudflare edge headers, and local development tunnels. |
| **`port_sweep.py`** | Startup diagnostic utility. Automatically terminates lingering zombie processes holding port 8000 on Windows/Linux, preventing `EADDRINUSE` launch crashes. |
| **`process_watchdog.py`** | Isolates background subprocesses (such as Cloudflare named tunnel agents) using Windows Job Objects so that shutting down the server cleanly terminates child processes. |
