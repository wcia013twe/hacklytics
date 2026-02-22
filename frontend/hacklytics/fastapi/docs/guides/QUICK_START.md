# Quick Start Guide

Fast setup for testing the Temporal RAG system.

---

## One-Command Setup

```bash
# From fastapi/ directory
make setup && make seed && make test-all
```

**Time:** ~2 minutes (container build + startup)

---

## Step-by-Step

### 1. Initialize Environment
```bash
make init          # Creates .env from .env.example
```

### 2. Build Containers
```bash
make build         # Builds rag, ingest, actian containers
```

### 3. Start Services
```bash
make up            # Starts all services in background
```

### 4. Verify Health
```bash
make health        # Checks ingest:8000, rag:8001, actian:5432
```

Expected output:
```json
Checking Ingest service...
{"status": "healthy"}

Checking RAG service...
{"status": "healthy", "actian_connected": true}

Checking Actian database...
/tmp:5432 - accepting connections
```

### 5. Seed Database
```bash
make seed          # Loads 10+ safety protocols
```

### 6. Run Tests
```bash
make test-all      # Runs all prompt tests (1-5)
```

---

## Test Individual Components

```bash
make test-prompt01   # Agents & Contracts
make test-prompt02   # Orchestrator Core
make test-prompt03   # Test Suites (7 profiles)
make test-prompt04   # Actian Setup
make test-prompt05   # E2E Integration
```

---

## Common Issues

### "Actian not ready"
```bash
docker logs hacklytics_actian
docker-compose restart actian
```

### "Protocol count is 0"
```bash
make seed
```

### "Tests not found"
```bash
make shell-rag
ls tests/
```

---

## Development Workflow

```bash
# Morning: Fresh start
make down && make up
make seed

# After code changes
docker-compose restart rag
make test-prompt01

# End of day: Full validation
make test-all
```

---

## Next Steps

- **View logs:** `make logs`
- **Database inspection:** `make db-verify`
- **Full guide:** See [Makefile Guide](MAKEFILE_GUIDE.md)
- **Architecture:** See [docs/overview/RAG.MD](../overview/RAG.MD)

---

**Time to productive testing:** < 3 minutes
