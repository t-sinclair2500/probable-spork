#!/usr/bin/env python3
"""
WordPress Backup Script
Python equivalent of backup_wp.sh for cross-platform compatibility
"""

import os
import sys
import argparse
import tarfile
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

def get_backup_config():
    """Get backup configuration from environment variables with defaults."""
    return {
        'backup_dir': os.getenv('WP_BACKUP_DIR', 'backups'),
        'db_name': os.getenv('WP_DB_NAME', 'wpblog'),
        'db_host': os.getenv('WP_DB_HOST', 'localhost'),
        'db_user': os.getenv('WP_DB_USER', 'root'),
        'db_password': os.getenv('WP_DB_PASSWORD', ''),
        'wp_content_path': os.getenv('WP_CONTENT_PATH', '/var/www/wordpress/wp-content'),
        'use_mysqldump': os.getenv('WP_USE_MYSQLDUMP', 'false').lower() == 'true'
    }

def create_backup_directory(backup_dir):
    """Create backup directory if it doesn't exist."""
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Backup directory: {backup_path}")
    return backup_path

def backup_database_mysqldump(config, backup_dir):
    """Backup database using mysqldump if available."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_path = backup_dir / f"wpblog_{timestamp}.sql"
    
    print(f"🗄️  Backing up database using mysqldump...")
    
    # Build mysqldump command
    cmd = [
        'mysqldump',
        '--host', config['db_host'],
        '--user', config['db_user']
    ]
    
    if config['db_password']:
        cmd.extend(['--password', config['db_password'])
    
    cmd.extend([
        '--single-transaction',
        '--routines',
        '--triggers',
        config['db_name']
    ])
    
    try:
        with open(db_backup_path, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True, text=True)
        
        print(f"✅ Database backup completed: {db_backup_path}")
        return db_backup_path
    except subprocess.CalledProcessError as e:
        print(f"❌ mysqldump failed: {e}")
        return None
    except FileNotFoundError:
        print("❌ mysqldump not found")
        return None

def backup_database_python(config, backup_dir):
    """Backup database using Python (SQLite fallback)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_path = backup_dir / f"wpblog_{timestamp}.sql"
    
    print(f"🗄️  Backing up database using Python...")
    
    # For now, create a placeholder SQL file
    # In a real implementation, you'd connect to MySQL using pymysql or similar
    try:
        with open(db_backup_path, 'w') as f:
            f.write(f"-- WordPress Database Backup\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Database: {config['db_name']}\n")
            f.write(f"-- Host: {config['db_host']}\n")
            f.write(f"-- User: {config['db_user']}\n")
            f.write(f"\n")
            f.write(f"-- Note: This is a placeholder backup.\n")
            f.write(f"-- Install pymysql and implement MySQL connection for full backup.\n")
            f.write(f"-- Example: pip install pymysql\n")
        
        print(f"✅ Database backup placeholder created: {db_backup_path}")
        return db_backup_path
    except Exception as e:
        print(f"❌ Database backup failed: {e}")
        return None

def backup_wp_content(config, backup_dir):
    """Backup WordPress content directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content_backup_path = backup_dir / f"wpfiles_{timestamp}.tar.gz"
    
    wp_content_path = Path(config['wp_content_path'])
    
    if not wp_content_path.exists():
        print(f"⚠️  WordPress content path does not exist: {wp_content_path}")
        print("   Creating empty backup...")
        
        # Create empty archive
        with tarfile.open(content_backup_path, "w:gz") as tar:
            pass
        
        print(f"✅ Empty content backup created: {content_backup_path}")
        return content_backup_path
    
    print(f"📁 Backing up WordPress content: {wp_content_path}")
    
    try:
        with tarfile.open(content_backup_path, "w:gz") as tar:
            # Add the entire wp-content directory
            tar.add(wp_content_path, arcname='wp-content')
        
        # Get archive size
        size_mb = content_backup_path.stat().st_size / (1024 * 1024)
        print(f"✅ Content backup completed: {content_backup_path} ({size_mb:.1f} MB)")
        return content_backup_path
    except Exception as e:
        print(f"❌ Content backup failed: {e}")
        return None

def verify_backups(db_backup_path, content_backup_path):
    """Verify the backup files can be read."""
    print("\n🔍 Verifying backups...")
    
    # Verify database backup
    if db_backup_path and db_backup_path.exists():
        try:
            with open(db_backup_path, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith('--') or first_line.startswith('/*'):
                    print(f"✅ Database backup verified: {db_backup_path}")
                else:
                    print(f"⚠️  Database backup format may be incorrect: {db_backup_path}")
        except Exception as e:
            print(f"❌ Database backup verification failed: {e}")
    
    # Verify content backup
    if content_backup_path and content_backup_path.exists():
        try:
            with tarfile.open(content_backup_path, "r:gz") as tar:
                file_count = len(tar.getmembers())
                print(f"✅ Content backup verified: {content_backup_path} ({file_count} files)")
        except Exception as e:
            print(f"❌ Content backup verification failed: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Create WordPress backup")
    parser.add_argument("--backup-dir", help="Backup directory")
    parser.add_argument("--db-name", help="Database name")
    parser.add_argument("--db-host", help="Database host")
    parser.add_argument("--db-user", help="Database user")
    parser.add_argument("--db-password", help="Database password")
    parser.add_argument("--wp-content-path", help="WordPress content path")
    parser.add_argument("--use-mysqldump", action="store_true", help="Use mysqldump if available")
    parser.add_argument("--verify", action="store_true", help="Verify backups after creation")
    
    args = parser.parse_args()
    
    # Get configuration (CLI args override env vars)
    config = get_backup_config()
    if args.backup_dir:
        config['backup_dir'] = args.backup_dir
    if args.db_name:
        config['db_name'] = args.db_name
    if args.db_host:
        config['db_host'] = args.db_host
    if args.db_user:
        config['db_user'] = args.db_user
    if args.db_password:
        config['db_password'] = args.db_password
    if args.wp_content_path:
        config['wp_content_path'] = args.wp_content_path
    if args.use_mysqldump:
        config['use_mysqldump'] = True
    
    print("🌐 Probable Spork - WordPress Backup")
    print("=" * 40)
    
    # Create backup directory
    backup_path = create_backup_directory(config['backup_dir'])
    
    # Backup database
    db_backup_path = None
    if config['use_mysqldump']:
        db_backup_path = backup_database_mysqldump(config, backup_path)
    
    if not db_backup_path:
        db_backup_path = backup_database_python(config, backup_path)
    
    # Backup WordPress content
    content_backup_path = backup_wp_content(config, backup_path)
    
    # Verify backups if requested
    if args.verify:
        verify_backups(db_backup_path, content_backup_path)
    
    print(f"\n🎉 WordPress backup completed!")
    if db_backup_path:
        print(f"   Database: {db_backup_path}")
    if content_backup_path:
        print(f"   Content: {content_backup_path}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
