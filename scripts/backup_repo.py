#!/usr/bin/env python3
"""
Repository Backup Script
Python equivalent of backup_repo.sh for cross-platform compatibility
"""

import os
import sys
import argparse
import tarfile
from datetime import datetime
from pathlib import Path

def get_backup_config():
    """Get backup configuration from environment variables with defaults."""
    # Use current directory as source if not specified
    current_dir = Path.cwd()
    
    return {
        'source': os.getenv('REPO_SOURCE', str(current_dir)),
        'backup_dir': os.getenv('REPO_BACKUP_DIR', str(current_dir / 'backups')),
        'include_patterns': [
            'data', 'scripts', 'assets', 'voiceovers', 
            'videos', 'jobs', 'conf', 'runs', 'exports'
        ],
        'exclude_patterns': [
            '.git', '.venv', 'venv', '__pycache__', 
            '*.pyc', '*.log', 'temp', 'cache'
        ]
    }

def create_backup_directory(backup_dir):
    """Create backup directory if it doesn't exist."""
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Backup directory: {backup_path}")
    return backup_path

def should_include_file(file_path, include_patterns, exclude_patterns):
    """Determine if a file should be included in the backup."""
    file_path_str = str(file_path)
    
    # Check if file matches any include pattern
    included = any(pattern in file_path_str for pattern in include_patterns)
    
    # Check if file matches any exclude pattern
    excluded = any(pattern in file_path_str for pattern in exclude_patterns)
    
    return included and not excluded

def create_backup_archive(source_dir, backup_dir, include_patterns, exclude_patterns):
    """Create a tar.gz backup archive."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_name = Path(source_dir).name
    archive_name = f"{source_name}_backup_{timestamp}.tar.gz"
    archive_path = backup_dir / archive_name
    
    print(f"📦 Creating backup archive: {archive_path}")
    print(f"   Source: {source_dir}")
    print(f"   Including: {', '.join(include_patterns)}")
    print(f"   Excluding: {', '.join(exclude_patterns)}")
    
    # Count files to be included
    total_files = 0
    total_size = 0
    
    with tarfile.open(archive_path, "w:gz") as tar:
        source_path = Path(source_dir)
        
        for root, dirs, files in os.walk(source_path):
            # Filter directories
            dirs[:] = [d for d in dirs if not any(ex in d for ex in exclude_patterns)]
            
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(source_path)
                
                if should_include_file(relative_path, include_patterns, exclude_patterns):
                    try:
                        tar.add(file_path, arcname=relative_path)
                        total_files += 1
                        total_size += file_path.stat().st_size
                        
                        if total_files % 100 == 0:
                            print(f"   Processed {total_files} files...")
                    except Exception as e:
                        print(f"⚠️  Warning: Could not add {file_path}: {e}")
    
    # Convert total size to human readable format
    size_mb = total_size / (1024 * 1024)
    print(f"✅ Backup completed: {total_files} files, {size_mb:.1f} MB")
    print(f"   Archive: {archive_path}")
    
    return archive_path

def verify_backup(archive_path):
    """Verify the backup archive can be read."""
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            file_count = len(tar.getmembers())
            print(f"🔍 Verification: Archive contains {file_count} files")
            return True
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Create repository backup")
    parser.add_argument("--source", help="Source directory to backup")
    parser.add_argument("--backup-dir", help="Backup directory")
    parser.add_argument("--include", nargs="+", help="Patterns to include")
    parser.add_argument("--exclude", nargs="+", help="Patterns to exclude")
    parser.add_argument("--verify", action="store_true", help="Verify backup after creation")
    
    args = parser.parse_args()
    
    # Get configuration (CLI args override env vars)
    config = get_backup_config()
    if args.source:
        config['source'] = args.source
    if args.backup_dir:
        config['backup_dir'] = args.backup_dir
    if args.include:
        config['include_patterns'] = args.include
    if args.exclude:
        config['exclude_patterns'] = args.exclude
    
    print("💾 Probable Spork - Repository Backup")
    print("=" * 40)
    
    # Validate source directory
    source_path = Path(config['source'])
    if not source_path.exists():
        print(f"❌ Source directory does not exist: {source_path}")
        sys.exit(1)
    
    if not source_path.is_dir():
        print(f"❌ Source is not a directory: {source_path}")
        sys.exit(1)
    
    print(f"📂 Source directory: {source_path}")
    
    # Create backup directory
    backup_path = create_backup_directory(config['backup_dir'])
    
    # Create backup archive
    try:
        archive_path = create_backup_archive(
            config['source'],
            backup_path,
            config['include_patterns'],
            config['exclude_patterns']
        )
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)
    
    # Verify backup if requested
    if args.verify:
        print("\n🔍 Verifying backup...")
        if not verify_backup(archive_path):
            print("❌ Backup verification failed")
            sys.exit(1)
        print("✅ Backup verification successful")
    
    print(f"\n🎉 Repository backup completed successfully!")
    print(f"   Backup location: {archive_path}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
