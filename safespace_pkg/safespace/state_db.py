"""
Persistent state storage for SafeSpace.

This module provides a lightweight SQLite database for storing and retrieving
environment state across sessions, enabling long-running test environments.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Set up logging
logger = logging.getLogger(__name__)

# Default database location in user home directory
DEFAULT_DB_PATH = Path.home() / ".config" / "safespace" / "environments.db"


class StateDatabase:
    """
    Lightweight SQLite database for persistent environment state storage.
    
    This class provides functionality for:
    - Storing environment state in a SQLite database
    - Retrieving environment state by ID or name
    - Listing available environments
    - Updating existing environment state
    - Deleting environment state
    """
    
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        """
        Initialize the state database.
        
        Args:
            db_path: Path to the SQLite database file (optional)
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._ensure_db_dir()
        self._init_db()
    
    def _ensure_db_dir(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create environments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS environments (
            id TEXT PRIMARY KEY,
            name TEXT,
            root_dir TEXT,
            created_at TEXT,
            last_accessed TEXT,
            state TEXT,
            metadata TEXT
        )
        ''')
        conn.commit()
        conn.close()
    
    def save_environment(self, 
                         env_id: str, 
                         name: Optional[str], 
                         root_dir: Path,
                         state: Dict[str, Any],
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save environment state to the database.
        
        Args:
            env_id: Unique environment ID
            name: Optional friendly name for the environment
            root_dir: Path to the environment root directory
            state: Dictionary containing environment state
            metadata: Optional metadata about the environment
            
        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Check if environment already exists
            cursor.execute("SELECT id FROM environments WHERE id = ?", (env_id,))
            exists = cursor.fetchone() is not None
            
            current_time = datetime.utcnow().isoformat()
            
            if exists:
                # Update existing environment
                cursor.execute('''
                UPDATE environments
                SET name = ?, root_dir = ?, last_accessed = ?, state = ?, metadata = ?
                WHERE id = ?
                ''', (
                    name, 
                    str(root_dir), 
                    current_time, 
                    json.dumps(state), 
                    json.dumps(metadata or {}),
                    env_id
                ))
            else:
                # Insert new environment
                cursor.execute('''
                INSERT INTO environments (id, name, root_dir, created_at, last_accessed, state, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    env_id,
                    name,
                    str(root_dir),
                    current_time,
                    current_time,
                    json.dumps(state),
                    json.dumps(metadata or {})
                ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save environment: {e}")
            return False
    
    def get_environment(self, 
                        env_id: Optional[str] = None, 
                        name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get environment state from the database.
        
        Args:
            env_id: Environment ID (optional if name is provided)
            name: Environment name (optional if env_id is provided)
            
        Returns:
            Dict containing environment data if found, None otherwise
        """
        if not env_id and not name:
            logger.error("Either env_id or name must be provided")
            return None
            
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Enable dictionary access
            cursor = conn.cursor()
            
            if env_id:
                cursor.execute("SELECT * FROM environments WHERE id = ?", (env_id,))
            else:
                cursor.execute("SELECT * FROM environments WHERE name = ?", (name,))
                
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
                
            # Update last accessed time
            current_time = datetime.utcnow().isoformat()
            cursor.execute('''
            UPDATE environments
            SET last_accessed = ?
            WHERE id = ?
            ''', (current_time, row['id']))
            
            conn.commit()
            
            # Convert row to dictionary
            env_data = dict(row)
            
            # Parse JSON fields
            env_data['state'] = json.loads(env_data['state'])
            env_data['metadata'] = json.loads(env_data['metadata'])
            
            conn.close()
            return env_data
        except Exception as e:
            logger.error(f"Failed to get environment: {e}")
            return None
    
    def list_environments(self) -> List[Dict[str, Any]]:
        """
        List all stored environments.
        
        Returns:
            List of dictionaries containing environment summary information
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, name, root_dir, created_at, last_accessed
            FROM environments
            ORDER BY last_accessed DESC
            ''')
            
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            environments = [dict(row) for row in rows]
            
            conn.close()
            return environments
        except Exception as e:
            logger.error(f"Failed to list environments: {e}")
            return []
    
    def delete_environment(self, env_id: str) -> bool:
        """
        Delete an environment from the database.
        
        Args:
            env_id: Environment ID to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM environments WHERE id = ?", (env_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            conn.close()
            
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete environment: {e}")
            return False
    
    def purge_old_environments(self, days: int = 30) -> int:
        """
        Purge environments that haven't been accessed in a specified number of days.
        
        Args:
            days: Number of days of inactivity before purging
            
        Returns:
            int: Number of environments purged
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Calculate cutoff date
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Delete old environments
            cursor.execute(
                "DELETE FROM environments WHERE last_accessed < ?", 
                (cutoff_date,)
            )
            
            purged = cursor.rowcount
            conn.commit()
            conn.close()
            
            return purged
        except Exception as e:
            logger.error(f"Failed to purge old environments: {e}")
            return 0


def get_state_db(db_path: Optional[Union[str, Path]] = None) -> StateDatabase:
    """
    Get a StateDatabase instance.
    
    Args:
        db_path: Optional custom database path
        
    Returns:
        StateDatabase instance
    """
    return StateDatabase(db_path) 