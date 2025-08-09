# Makefile for Signals Agent

.PHONY: help test test-local test-prod pre-deploy deploy post-deploy clean setup

help:
	@echo "Available commands:"
	@echo "  make setup        - Install dependencies and initialize database"
	@echo "  make test         - Run all tests locally"
	@echo "  make test-local   - Run E2E tests against local server"
	@echo "  make test-prod    - Run E2E tests against production"
	@echo "  make pre-deploy   - Run pre-deployment validation"
	@echo "  make deploy       - Deploy to production (with validation)"
	@echo "  make post-deploy  - Verify deployment"
	@echo "  make clean        - Clean up temporary files"

setup:
	@echo "Setting up environment..."
	uv pip install fastmcp pydantic rich google-generativeai requests fastapi uvicorn
	@if [ \! -f config.json ]; then cp config.json.sample config.json; fi
	uv run python database.py
	@echo "Setup complete\!"

test: test-local

test-local:
	@echo "Running local E2E tests..."
	@uv run python test_e2e.py http://localhost:8000

test-prod:
	@echo "Running production E2E tests..."
	@uv run python test_e2e.py --production

test-routing:
	@echo "Running routing tests..."
	@uv run python test_routing.py http://localhost:8000

test-routing-prod:
	@echo "Running routing tests against production..."
	@uv run python test_routing.py https://audience-agent.fly.dev

pre-deploy:
	@echo "Running pre-deployment validation..."
	@uv run python pre_deploy_check.py

deploy: pre-deploy
	@echo "Deploying to production..."
	fly deploy --no-cache
	@echo "Waiting for deployment to stabilize..."
	@sleep 15
	@echo "Running post-deployment verification..."
	@uv run python post_deploy_verify.py

post-deploy:
	@echo "Verifying deployment..."
	@uv run python post_deploy_verify.py

clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -f .coverage 2>/dev/null || true
	@echo "Cleanup complete\!"

# Development helpers
run-local:
	@echo "Starting local server on port 8000..."
	uv run uvicorn unified_server:app --reload

run-local-test:
	@echo "Starting local server on port 8765 for testing..."
	uv run uvicorn unified_server:app --port 8765

# Quick deployment without full validation (use with caution)
quick-deploy:
	@echo "Quick deployment (no validation)..."
	fly deploy --no-cache

# Database operations
db-reset:
	@echo "Resetting database..."
	@rm -f signals_agent.db
	@uv run python database.py
	@echo "Database reset complete\!"

db-inspect:
	@echo "Database tables:"
	@sqlite3 signals_agent.db ".tables"
	@echo "\nSignal segments:"
	@sqlite3 signals_agent.db "SELECT id, name FROM signal_segments LIMIT 5;"

# Git operations
commit-and-push:
	@git add -A
	@git commit -m "Update from automated testing"
	@git push

# Full workflow
full-test-and-deploy: pre-deploy deploy
	@echo "Full test and deployment complete\!"
EOF < /dev/null