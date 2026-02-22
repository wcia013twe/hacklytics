#!/bin/bash
# Setup script for Actian VectorAI DB from official TAR file
# Usage: ./setup_vectoraidb_from_tar.sh /path/to/Actian_VectorAI_DB_Beta.tar

set -e  # Exit on error

echo "=================================================="
echo "Actian VectorAI DB Setup from TAR"
echo "=================================================="

# Check if TAR file path provided
if [ -z "$1" ]; then
    echo "❌ ERROR: No TAR file specified"
    echo ""
    echo "Usage: $0 /path/to/Actian_VectorAI_DB_Beta.tar"
    echo ""
    echo "Please download the official TAR file from:"
    echo "  - Hacklytics Slack/Discord"
    echo "  - Hackathon organizers"
    echo ""
    exit 1
fi

TAR_FILE="$1"

# Check if TAR file exists
if [ ! -f "$TAR_FILE" ]; then
    echo "❌ ERROR: TAR file not found: $TAR_FILE"
    exit 1
fi

echo ""
echo "[1/5] Stopping existing VectorAI DB container..."
docker compose down vectoraidb 2>/dev/null || echo "  (no existing container)"

echo ""
echo "[2/5] Removing old image (if exists)..."
docker rmi williamimoh/actian-vectorai-db:1.0b 2>/dev/null || echo "  (no old image to remove)"
docker rmi localhost/actian/vectoraidb:1.0b 2>/dev/null || echo "  (no existing image)"

echo ""
echo "[3/5] Loading image from TAR file: $TAR_FILE"
docker image load -i "$TAR_FILE"

echo ""
echo "[4/5] Verifying image loaded..."
if docker images localhost/actian/vectoraidb:1.0b | grep -q vectoraidb; then
    echo "  ✅ Image loaded successfully:"
    docker images localhost/actian/vectoraidb:1.0b
else
    echo "  ❌ ERROR: Image failed to load"
    exit 1
fi

echo ""
echo "[5/5] Starting VectorAI DB container..."
docker compose up -d vectoraidb

echo ""
echo "=================================================="
echo "Waiting for VectorAI DB to start (60 seconds)..."
echo "=================================================="
sleep 60

echo ""
echo "Checking container status..."
docker ps --filter "name=hacklytics_vectoraidb" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "Checking server process..."
docker exec hacklytics_vectoraidb ps aux | grep vdss-grpc-server || echo "⚠️  Server process not found"

echo ""
echo "=================================================="
echo "Next Steps:"
echo "=================================================="
echo ""
echo "1. Test connectivity with Python client:"
echo "   python3 test_vectoraidb_connection.py"
echo ""
echo "2. Check logs if issues occur:"
echo "   docker logs hacklytics_vectoraidb"
echo "   docker exec hacklytics_vectoraidb cat /data/vde.log"
echo ""
echo "3. Start remaining services:"
echo "   docker compose up -d"
echo ""
