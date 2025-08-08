.PHONY: test test-a2a test-all server test-server install clean deploy setup-hooks

# Default target
help:
	@echo "Available targets:"
	@echo "  make test        - Run A2A compatibility tests (with mocks)"
	@echo "  make test-all    - Run all tests (with mocks)"
	@echo "  make server      - Start the development server"
	@echo "  make test-server - Start server with mocked Gemini"
	@echo "  make install     - Install dependencies"
	@echo "  make deploy      - Deploy to Fly.dev"
	@echo "  make setup-hooks - Install git hooks"
	@echo "  make clean       - Clean up temporary files"

# Install dependencies
install:
	uv pip install pytest requests pydantic google-generativeai fastapi uvicorn httpx fastmcp rich

# Run tests
test:
	@echo "Running A2A compatibility tests with mocked Gemini..."
	@TEST_MODE=true uv run python run_tests.py --a2a-only -v --with-server

test-all:
	@echo "Running all tests with mocked Gemini..."
	@TEST_MODE=true uv run python run_tests.py -v --with-server

# Start server
server:
	@echo "Starting server on http://localhost:8000"
	uv run python unified_server_v2.py

# Start test server with mocks
test-server:
	@echo "Starting test server with mocked Gemini on http://localhost:8000"
	@TEST_MODE=true uv run python unified_server_v2.py

# Deploy to Fly.dev
deploy:
	@echo "Deploying to Fly.dev..."
	fly deploy

# Setup git hooks
setup-hooks:
	@echo "Setting up git hooks..."
	@cp .git-hooks/pre-commit .git/hooks/pre-commit 2>/dev/null || true
	@cp .git-hooks/pre-push .git/hooks/pre-push 2>/dev/null || true
	@chmod +x .git/hooks/* 2>/dev/null || true
	@echo "Git hooks installed!"

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true