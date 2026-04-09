## 🏗️ Project Layout & Architecture

This project follows a **Clean Architecture** pattern, enforcing a strict separation of concerns through a standards-based directory structure.

```text
job_queue/
├── cmd/                # Entrypoints (CLI / Future API)
├── internal/           # Private application code (Non-importable)
│   ├── domain/         # 🧠 Core logic: State Machines & Entities
│   ├── application/    # ⚙️ Use Cases: Orchestrating the flow
│   ├── service/        # 🛠️ Domain Services: State enforcement
│   ├── repository/     # 🗄️ Persistence Abstraction (Interfaces)
│   └── infra/          # 🧩 Infrastructure: Time, ID, Logging
├── migrations/         # DB Schema Evolution
├── tests/              # 🧪 Unified Test Suite (Unit & Integration)
└── docs/               # Technical Whitepapers & Design Docs

Engineering Note:
By isolating the domain from infra, we ensure the core business logic (Lease management, Retry policies) remains 100% testable and decoupled from the underlying database (SQLite/PostgreSQL).