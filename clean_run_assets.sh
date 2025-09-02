#!/bin/bash

# Clean Run Assets Script
# Removes all generated run-related files and directories

set -e

echo "Cleaning run-related assets..."

# Function to safely remove directory contents
clean_directory() {
    local dir="$1"
    local description="$2"
    
    if [ -d "$dir" ] && [ "$(ls -A "$dir" 2>/dev/null)" ]; then
        echo "Removing $description..."
        rm -rf "$dir"/*
        echo "✓ Cleaned $description"
    else
        echo "✓ $description already clean"
    fi
}

# Function to safely remove file
clean_file() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        echo "Removing $description..."
        rm -f "$file"
        echo "✓ Removed $description"
    else
        echo "✓ $description already clean"
    fi
}

# Clean directories
clean_directory "runs" "run output directories"
clean_directory "render_cache" "render cache files"
clean_directory "data/cache" "data cache files"
clean_directory "temp_export" "temporary export files"
clean_directory "logs" "log files"
clean_directory "assets/generated" "generated SVG assets"
clean_directory "voiceovers" "generated voiceover files"
clean_directory "videos" "generated video files"
clean_directory "reports" "generated reports"
clean_directory "results" "generated results"

# Clean individual files
clean_file "jobs/state.jsonl" "job state tracking file"
clean_file "jobs.db" "jobs database"
clean_file "data/research.db" "research database"
clean_file "data/trending_topics.db" "trending topics database"

echo ""
echo "✓ All run-related assets cleaned successfully!"
echo ""
echo "Cleaned directories:"
echo "  - runs/*"
echo "  - render_cache/*"
echo "  - data/cache/*"
echo "  - temp_export/*"
echo "  - logs/*"
echo "  - assets/generated/*"
echo "  - voiceovers/*"
echo "  - videos/*"
echo "  - reports/*"
echo "  - results/*"
echo ""
echo "Cleaned files:"
echo "  - jobs/state.jsonl"
echo "  - jobs.db"
echo "  - data/research.db"
echo "  - data/trending_topics.db"
