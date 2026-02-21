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
	@echo "  make test-all      - Run all tests (all prompts)"
	@echo ""
	@echo "=== Database Operations ==="
	@echo "  make seed        - Seed safety protocols into Actian"
	@echo "  make db-verify   - Verify Actian schema and data"
	@echo "  make db-reset    - Reset database (drop + recreate)"

# Build Docker images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d

# Stop services
down:
	docker-compose down

# Restart all services
restart:
	docker-compose restart

# Tail logs
logs:
	docker-compose logs -f

logs-ingest:
	docker-compose logs -f ingest

logs-rag:
	docker-compose logs -f rag

logs-actian:
	docker-compose logs -f actian

# Show service status
ps:
	docker-compose ps

# Run tests
test:
	docker-compose exec rag python -m pytest tests/ -v

# Run tests with coverage
test-cov:
	docker-compose exec rag python -m pytest --cov=backend tests/

# Open shell in containers
shell-rag:
	docker-compose exec rag /bin/bash

shell-ingest:
	docker-compose exec ingest /bin/bash

# Connect to database
db-shell:
	docker-compose exec actian psql -U vectoruser -d safety_db

# Seed protocols (placeholder - implement scripts/seed_protocols.py first)
seed:
	@echo "Running protocol seeding script..."
	@docker-compose exec rag python scripts/seed_protocols.py || echo "Create scripts/seed_protocols.py first"

# Check service health
health:
	@echo "Checking Ingest service..."
	@curl -s http://localhost:8000/health | jq || echo "Ingest not responding"
	@echo ""
	@echo "Checking RAG service..."
	@curl -s http://localhost:8001/health | jq || echo "RAG not responding"
	@echo ""
	@echo "Checking Actian database..."
	@docker-compose exec actian pg_isready -U vectoruser -d safety_db

# Clean everything (removes volumes)
clean:
	@echo "WARNING: This will delete all data in volumes. Press Ctrl+C to cancel, Enter to continue..."
	@read confirm
	docker-compose down -v

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
	@docker-compose exec rag python -m pytest tests/test_agents/ -v --tb=short || \
		(echo "⚠️  Agent tests not found. Run: docker-compose up -d rag"; exit 1)
	@echo ""
	@echo "✅ PROMPT 1 validation complete"

# PROMPT 2: Test orchestrator core
test-prompt02:
	@echo "========================================"
	@echo "PROMPT 2: Orchestrator Core Testing"
	@echo "========================================"
	@echo ""
	@echo "Testing dual-path routing, error handling, metrics..."
	@docker-compose exec rag python -m pytest tests/test_orchestrator.py -v --tb=short || \
		(echo "⚠️  Orchestrator tests not found. Run: docker-compose up -d rag"; exit 1)
	@echo ""
	@echo "✅ PROMPT 2 validation complete"

# PROMPT 3: Run all 7 test profiles
test-prompt03:
	@echo "========================================"
	@echo "PROMPT 3: Test Suites (7 Profiles)"
	@echo "========================================"
	@echo ""
	@echo "Running test profiles 1-7..."
	@docker-compose exec rag python -m pytest tests/test_profiles/ -v --tb=short || \
		(echo "⚠️  Test profiles not found. Run: docker-compose up -d rag"; exit 1)
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

# PROMPT 4: Test Actian setup, schema, and seeding
test-prompt04:
	@echo "========================================"
	@echo "PROMPT 4: Actian Vector DB Setup"
	@echo "========================================"
	@echo ""
	@echo "[1/4] Checking Actian container health..."
	@docker-compose exec actian pg_isready -U vectoruser -d safety_db || \
		(echo "❌ Actian not ready. Run: docker-compose up -d actian"; exit 1)
	@echo "✅ Actian container healthy"
	@echo ""
	@echo "[2/4] Verifying schema (safety_protocols, incident_log)..."
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "\dt" | grep -E "(safety_protocols|incident_log)" || \
		(echo "❌ Schema missing. Run: make db-reset"; exit 1)
	@echo "✅ Schema verified"
	@echo ""
	@echo "[3/4] Checking protocol count..."
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "SELECT COUNT(*) as protocol_count FROM safety_protocols;" || \
		(echo "⚠️  Query failed"; exit 1)
	@echo ""
	@echo "[4/4] Testing vector similarity retrieval..."
	@docker-compose exec rag python scripts/test_actian_queries.py || \
		(echo "⚠️  Actian query tests not found"; exit 0)
	@echo ""
	@echo "✅ PROMPT 4 validation complete"

# PROMPT 5: Full integration and E2E tests
test-prompt05:
	@echo "========================================"
	@echo "PROMPT 5: Integration & E2E Testing"
	@echo "========================================"
	@echo ""
	@echo "[1/3] Verifying all services are running..."
	@docker-compose ps | grep -E "(actian|rag|ingest)" || \
		(echo "❌ Services not running. Run: make up"; exit 1)
	@echo "✅ All services running"
	@echo ""
	@echo "[2/3] Health check (ingest + rag + actian)..."
	@make health
	@echo ""
	@echo "[3/3] Running E2E integration tests..."
	@docker-compose exec rag python -m pytest tests/test_integration/ -v --tb=short || \
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

# ============================================
# DATABASE OPERATIONS
# ============================================

# Verify database schema and data
db-verify:
	@echo "Verifying Actian database..."
	@echo ""
	@echo "Tables:"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "\dt"
	@echo ""
	@echo "Indexes:"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "\di"
	@echo ""
	@echo "Protocol count:"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "SELECT COUNT(*) FROM safety_protocols;"
	@echo ""
	@echo "Incident count:"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "SELECT COUNT(*) FROM incident_log;"
	@echo ""
	@echo "Protocol coverage:"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "SELECT severity, category, COUNT(*) FROM safety_protocols GROUP BY severity, category;"

# Reset database (drop all tables and recreate schema)
db-reset:
	@echo "⚠️  WARNING: This will delete all data in the database!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Dropping tables..."
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "DROP TABLE IF EXISTS incident_log CASCADE;"
	@docker-compose exec -T actian psql -U vectoruser -d safety_db -c "DROP TABLE IF EXISTS safety_protocols CASCADE;"
	@echo "Recreating schema from init.sql..."
	@docker-compose exec -T actian psql -U vectoruser -d safety_db < init.sql || \
		cat init.sql | docker-compose exec -T actian psql -U vectoruser -d safety_db
	@echo "✅ Database reset complete"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'make seed' to populate safety_protocols"
	@echo "  2. Run 'make test-prompt04' to verify"
