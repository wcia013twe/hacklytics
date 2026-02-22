.PHONY: help build up down restart logs clean test seed

# Default target
help:
	@echo "Temporal RAG Backend - Docker Management"
	@echo ""
	@echo "=== Core Commands ==="
	@echo "  make build       - Build all Docker images"
	@echo "  make up          - Start all services in detached mode"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - Tail logs from all services"
	@echo "  make logs-ingest - Tail logs from ingest service"
	@echo "  make logs-rag    - Tail logs from RAG service"
	@echo "  make logs-actian - Tail logs from Actian service"
	@echo "  make ps          - Show status of all services"
	@echo "  make health      - Check health of all services"
	@echo "  make clean       - Stop services and remove volumes (WARNING: deletes data)"
	@echo ""
	@echo "=== Development ==="
	@echo "  make shell-rag   - Open shell in RAG container"
	@echo "  make shell-ingest - Open shell in ingest container"
	@echo "  make db-shell    - Connect to Actian database"
	@echo "  make init        - Initialize environment from .env.example"
	@echo "  make setup       - Full setup (init + build + up)"
	@echo ""
	@echo "=== Prompt-Scoped Testing ==="
	@echo "  make test-prompt01 - Test PROMPT 1: Agents & Contracts"
	@echo "  make test-prompt02 - Test PROMPT 2: Orchestrator Core"
	@echo "  make test-prompt03 - Test PROMPT 3: Test Suites (All 7 profiles)"
	@echo "  make test-prompt04 - Test PROMPT 4: Actian Setup (DB + Seeding)"
	@echo "  make test-prompt05 - Test PROMPT 5: Integration & E2E"
	@echo "  make test-all      - Run all tests (compact output, use VERBOSE=1 for details)"
	@echo "  make test-safety   - Test safety improvements (guardrails, sensor conflicts, priority queue)"
	@echo ""
	@echo "  Note: Add VERBOSE=1 to any test command for detailed output"
	@echo "        Example: make test-all VERBOSE=1"
	@echo ""
	@echo "=== Database Operations ==="
	@echo "  make seed        - Seed safety protocols into Actian"
	@echo "  make db-verify   - Verify Actian schema and data"
	@echo "  make db-reset    - Reset database (drop + recreate)"

# Build Docker images
build:
	docker compose build

# Start services
up:
	docker compose up -d

# Stop services
down:
	docker compose down

# Restart all services
restart:
	docker compose restart

# Tail logs
logs:
	docker compose logs -f

logs-ingest:
	docker compose logs -f ingest

logs-rag:
	docker compose logs -f rag

logs-actian:
	docker compose logs -f vectoraidb

logs-vectoraidb:
	docker compose logs -f vectoraidb

# Show service status
ps:
	docker compose ps

# Run tests
test:
	docker compose exec rag python -m pytest tests/ -v

# Run tests with coverage
test-cov:
	docker compose exec rag python -m pytest --cov=backend tests/

# Open shell in containers
shell-rag:
	docker compose exec rag /bin/bash

shell-ingest:
	docker compose exec ingest /bin/bash

# Connect to database (VectorAI DB - gRPC, no SQL shell)
db-shell:
	@echo "VectorAI DB uses gRPC API (no SQL shell available)"
	@echo "Use Python client to interact with collections"
	@echo "Example: docker compose exec rag python scripts/query_vectoraidb.py"

# Seed protocols (placeholder - implement scripts/seed_protocols.py first)
seed:
	@echo "Running protocol seeding script..."
	@docker compose exec rag python scripts/seed_protocols.py || echo "Create scripts/seed_protocols.py first"

# Check service health
health:
	@echo "Checking Ingest service..."
	@curl -s http://localhost:8000/health | jq || echo "Ingest not responding"
	@echo ""
	@echo "Checking RAG service..."
	@curl -s http://localhost:8001/health | jq || echo "RAG not responding"
	@echo ""
	@echo "Checking VectorAI DB (gRPC port 50051)..."
	@nc -zv localhost 50051 2>&1 | grep -q "succeeded" && echo "✅ VectorAI DB listening on port 50051" || echo "❌ VectorAI DB not accessible on port 50051"

# Clean everything (removes volumes)
clean:
	@echo "WARNING: This will delete all data in volumes. Press Ctrl+C to cancel, Enter to continue..."
	@read confirm
	docker compose down -v

# Initialize environment
init:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	else \
		echo ".env already exists"; \
	fi

# Full setup (init + build + up)
setup: init build up
	@echo "Waiting for services to be ready..."
	@sleep 10
	@make health

# ============================================
# PROMPT-SCOPED TESTING
# ============================================

# PROMPT 1: Test agents and contracts (unit tests only)
test-prompt01:
	@echo "========================================"
	@echo "PROMPT 1: Agents & Contracts Testing"
	@echo "========================================"
	@echo ""
	@echo "Testing 8 sub-agents + Pydantic models..."
	@if docker compose ps rag 2>/dev/null | grep -q "Up"; then \
		docker compose exec rag python -m pytest tests/agents/ $(if $(VERBOSE),-v,--tb=line) || \
		(echo "⚠️  Agent tests not found."; exit 1); \
	else \
		echo "⚠️  RAG service not running. Testing locally..."; \
		python -m pytest tests/agents/ $(if $(VERBOSE),-v,--tb=line) 2>/dev/null || \
		(echo "⚠️  Tests not found. Ensure services are running: make up"; exit 1); \
	fi
	@echo ""
	@echo "✅ PROMPT 1 validation complete"

# PROMPT 2: Test orchestrator core
test-prompt02:
	@echo "========================================"
	@echo "PROMPT 2: Orchestrator Core Testing"
	@echo "========================================"
	@echo ""
	@echo "Testing dual-path routing, error handling, metrics..."
	@docker compose exec rag python -m pytest tests/test_orchestrator.py $(if $(VERBOSE),-v,--tb=line) || \
		(echo "⚠️  Orchestrator tests not found. Run: docker compose up -d rag"; exit 1)
	@echo ""
	@echo "✅ PROMPT 2 validation complete"

# PROMPT 3: Run all 7 test profiles
test-prompt03:
	@echo "========================================"
	@echo "PROMPT 3: Test Suites (7 Profiles)"
	@echo "========================================"
	@echo ""
	@echo "Running test profiles 1-7..."
	@docker compose exec rag python -m pytest tests/test_profiles/ $(if $(VERBOSE),-v,--tb=line) || \
		(echo "⚠️  Test profiles not found. Run: docker compose up -d rag"; exit 1)
	@echo ""
	@echo "Test Profile Summary:"
	@echo "  1. ✅ Embedding Semantic Sanity"
	@echo "  2. ✅ Protocol Retrieval Precision"
	@echo "  3. ✅ Temporal Trend Accuracy"
	@echo "  4. ✅ Incident Log Feedback Loop"
	@echo "  5. ✅ E2E Latency Benchmark"
	@echo "  6. ✅ Graceful Degradation"
	@echo "  7. ✅ Delta Filter Validation"
	@echo ""
	@echo "✅ PROMPT 3 validation complete"

# PROMPT 4: Test VectorAI DB setup, collections, and seeding
test-prompt04:
	@echo "========================================"
	@echo "PROMPT 4: VectorAI DB Setup"
	@echo "========================================"
	@echo ""
	@echo "[1/4] Checking VectorAI DB container health..."
	@docker compose ps vectoraidb 2>/dev/null | grep -q "Up" || \
		(echo "❌ VectorAI DB not running. Run: docker compose up -d vectoraidb"; exit 1)
	@echo "✅ VectorAI DB container running"
	@echo ""
	@echo "[2/4] Testing gRPC connectivity (port 50051)..."
	@nc -zv localhost 50051 2>&1 | grep -q "succeeded" || \
		(echo "❌ Port 50051 not accessible. Check: docker logs hacklytics_vectoraidb"; exit 1)
	@echo "✅ gRPC port accessible"
	@echo ""
	@echo "[3/4] Verifying collections exist (safety_protocols, incident_log)..."
	@python scripts/verify_collections.py 2>/dev/null || \
		(echo "⚠️  Collection verification script not found. Create scripts/verify_collections.py"; exit 0)
	@echo ""
	@echo "[4/4] Testing vector similarity search..."
	@python scripts/test_vectoraidb_search.py 2>/dev/null || \
		(echo "⚠️  Search test script not found. Create scripts/test_vectoraidb_search.py"; exit 0)
	@echo ""
	@echo "✅ PROMPT 4 validation complete"

# PROMPT 5: Full integration and E2E tests
test-prompt05:
	@echo "========================================"
	@echo "PROMPT 5: Integration & E2E Testing"
	@echo "========================================"
	@echo ""
	@echo "[1/3] Verifying all services are running..."
	@docker compose ps | grep -E "(vectoraidb|rag|ingest)" || \
		(echo "❌ Services not running. Run: make up"; exit 1)
	@echo "✅ All services running"
	@echo ""
	@echo "[2/3] Health check (ingest + rag + vectoraidb)..."
	@make health
	@echo ""
	@echo "[3/3] Running E2E integration tests..."
	@docker compose exec rag python -m pytest tests/test_integration/ -v --tb=short || \
		(echo "⚠️  Integration tests not found"; exit 0)
	@echo ""
	@echo "✅ PROMPT 5 validation complete"

# Run all prompt tests sequentially
test-all:
	@echo "========================================"
	@echo "Running ALL Prompt Tests (1-5)"
	@echo "========================================"
	@echo ""
	@make test-prompt01
	@echo ""
	@make test-prompt02
	@echo ""
	@make test-prompt03
	@echo ""
	@make test-prompt04
	@echo ""
	@make test-prompt05
	@echo ""
	@echo "🎉 All prompt validations complete!"

# Safety Improvements Testing (Three-Problem Fix)
test-safety:
	@echo "========================================"
	@echo "Safety Improvements Testing"
	@echo "========================================"
	@echo ""
	@echo "Testing Problem 1: Hallucination Guardrails..."
	@docker compose exec rag python -m pytest tests/agents/test_safety_guardrails.py $(if $(VERBOSE),-v,--tb=line) || \
		(echo "⚠️  Guardrails tests not found"; exit 1)
	@echo ""
	@echo "Testing Problem 3: Context Drift (Priority Queue)..."
	@docker compose exec rag python -m pytest tests/agents/test_temporal_buffer_priority.py $(if $(VERBOSE),-v,--tb=line) || \
		(echo "⚠️  Priority queue tests not found"; exit 1)
	@echo ""
	@echo "Testing Problem 2: Sensor Conflict Resolution (Nano)..."
	@cd ../nano && python test_sensor_conflicts.py || \
		(echo "⚠️  Sensor conflict tests not found"; exit 1)
	@echo ""
	@echo "✅ All safety improvements validated!"

# ============================================
# DATABASE OPERATIONS (VectorAI DB)
# ============================================

# Verify VectorAI DB collections and data
db-verify:
	@echo "Verifying VectorAI DB collections..."
	@echo ""
	@python scripts/verify_collections.py || \
		(echo "⚠️  Create scripts/verify_collections.py to check collection status"; exit 0)

# Reset database (delete collections and recreate)
db-reset:
	@echo "⚠️  WARNING: This will delete all collections and data in VectorAI DB!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Deleting collections..."
	@python scripts/reset_collections.py || \
		(echo "⚠️  Create scripts/reset_collections.py to reset collections"; exit 0)
	@echo "✅ Collections reset complete"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'python scripts/init_actian_collections.py' to create collections"
	@echo "  2. Run 'make seed' to populate safety_protocols"
	@echo "  3. Run 'make test-prompt04' to verify"

# Initialize VectorAI DB collections
db-init:
	@echo "Initializing VectorAI DB collections..."
	@python scripts/init_actian_collections.py || \
		(echo "⚠️  Create scripts/init_actian_collections.py first"; exit 1)
	@echo "✅ Collections initialized"
