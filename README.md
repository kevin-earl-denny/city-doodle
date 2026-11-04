# City Doodle

A lo-fi vector city builder — a lightweight planning sim disguised as a map doodle. Generate believable terrain, place districts and infrastructure, simulate organic city growth over time, and export beautiful artifacts.

## Features

- **Terrain Generation**: Server-side procedural terrain with seamless 3×3 tile neighborhoods
- **City Building**: Place districts, POIs, and transit with snap-to-geometry
- **Growth Simulation**: Watch your city evolve over 1, 5, or 10 year time steps
- **Metrics**: VMT-lite tracking (Vehicle Miles Traveled, transit ridership proxy)
- **Historic Preservation**: Mark districts as historic to prevent redevelopment
- **Export**: PNG snapshots and GIF timelapses of your city's evolution
- **Handwritten Labels**: Charming map labels with deterministic placement
- **Personality Sliders**: Customize city character (Grid↔Organic, Sprawl↔Compact, etc.)

## Architecture

```
city-doodle/
├── apps/
│   ├── web/          # React + TypeScript + PixiJS frontend
│   ├── api/          # FastAPI backend
│   └── worker/       # Python worker for heavy generation tasks
├── packages/
│   └── shared/       # Shared TypeScript types + Python schemas
├── lib/              # Development tooling (vibe CLI)
└── recipes/          # Development workflow guides
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + TypeScript + Vite + PixiJS (WebGL) |
| **Backend** | FastAPI (Python 3.11+) |
| **Worker** | Python background jobs for terrain generation |
| **Database** | PostgreSQL (Neon) |
| **Deployment** | Vercel (web), Fly.io (API + worker) |

## Getting Started

### Prerequisites

- Node.js >= 18
- Python >= 3.11
- npm (comes with Node.js)

### Installation

```bash
# Install Node dependencies
npm install

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python packages in development mode
pip install -e ".[dev]"
pip install -e "apps/api[dev]"
pip install -e apps/worker
pip install -e packages/shared

# Enable the repo's git hooks (once per clone; covers every worktree)
git config --local core.hooksPath .githooks
```

The hooks in `.githooks/`:

- **pre-commit** refuses any `.env` / `.env.*` file except `.env.example`, and runs `gitleaks protect --staged` if gitleaks is installed.
- **pre-push** runs `ruff check` + `ruff format --check` on changed Python files under `apps/api`, `apps/worker` and `lib`, `eslint` on changed `apps/web` files, and `tsc --noEmit` when `apps/web` or `packages/` changed. It also warns if the Alembic chain is broken. A missing tool blocks the push (run `npm install`, install ruff). Bypass with `git push --no-verify` only if you've checked another way.

`bin/vibe doctor` warns when `core.hooksPath` isn't set.

### Migrations

`bin/migrations check` exits 1 on multiple Alembic heads or a duplicate revision ID (2 if alembic itself can't run). `bin/migrations heads` lists heads; `bin/migrations fix-heads` generates the merge migration. CI runs the check on every PR ("Assert single Alembic head").

### Running the Apps

```bash
# Web app (development server)
npm run dev

# API server (activate venv first)
source .venv/bin/activate
uvicorn city_api.main:app --reload --app-dir apps/api/src

# Worker
source .venv/bin/activate
python -m city_worker.main
```

### Running Tests

```bash
# Python tests (API)
source .venv/bin/activate
pytest apps/api/tests -v

# TypeScript tests (Web)
npm test --workspace=apps/web
```

## API Documentation

When the API server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | AI agent instructions and development workflows |
| [01_lofi_city_builder_overview_tests.md](./01_lofi_city_builder_overview_tests%20(1).md) | Product overview and testable functionality |
| [02_ai_coding_assistant_prompt_milestones.md](./02_ai_coding_assistant_prompt_milestones.md) | V1 milestone plan |
| [03_v2_improvements_milestones.md](./03_v2_improvements_milestones.md) | V2 roadmap (needs system, 3D view, multiplayer) |

## Development Workflow

This project uses a ticket-driven development workflow with Linear for issue tracking. See [CLAUDE.md](./CLAUDE.md) for:

- Creating and working on tickets
- Git worktree workflow for parallel development
- PR guidelines and CI requirements
- Label conventions (type, risk, area)

## License

MIT
