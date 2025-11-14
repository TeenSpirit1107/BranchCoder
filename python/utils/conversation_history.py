#!/usr/bin/env python3
"""
Conversation History Manager
Manages conversation history for AI service, persisting to disk for session continuity.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from utils.logger import Logger

logger = Logger('conversation_history', log_to_file=False)

# Default history file location
DEFAULT_HISTORY_DIR = Path.home() / ".vscode-branch-coder"
DEFAULT_HISTORY_FILE = DEFAULT_HISTORY_DIR / "conversation_history.json"


class ConversationHistory:
    """Manages conversation history with file-based persistence."""
    
    def __init__(self, history_file: Optional[str] = None):
        """
        Initialize conversation history manager.
        
        Args:
            history_file: Path to history file (default: ~/.vscode-branch-coder/conversation_history.json)
        """
        self.history_file = Path(history_file) if history_file else DEFAULT_HISTORY_FILE
        self._ensure_history_dir()
        self._histories: Dict[str, List[Dict[str, str]]] = {}
        self._load_all_histories()
    
    def _ensure_history_dir(self):
        """Ensure the history directory exists."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create history directory: {e}")
    
    def _load_all_histories(self):
        """Load all conversation histories from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._histories = json.load(f)
                logger.debug(f"Loaded {len(self._histories)} conversation histories")
            else:
                self._histories = {}
                logger.debug("No existing history file found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load history file: {e}")
            self._histories = {}
    
    def _save_all_histories(self):
        """Save all conversation histories to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._histories, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self._histories)} conversation histories")
        except Exception as e:
            logger.error(f"Failed to save history file: {e}")
    
    def get_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier (default: "default")
        
        Returns:
            List of messages in format [{"role": "user|assistant", "content": "..."}]
        """
        return self._histories.get(session_id, []).copy()
    
    def add_message(self, role: str, content: str, session_id: str = "default"):
        """
        Add a message to conversation history.
        
        Args:
            role: Message role ("user" or "assistant")
            content: Message content
            session_id: Session identifier (default: "default")
        """
        if session_id not in self._histories:
            self._histories[session_id] = []
        
        self._histories[session_id].append({
            "role": role,
            "content": content
        })
        
        # Limit history length to prevent excessive token usage
        # Keep last 50 messages (25 user + 25 assistant pairs)
        max_messages = 50
        if len(self._histories[session_id]) > max_messages:
            self._histories[session_id] = self._histories[session_id][-max_messages:]
        
        self._save_all_histories()
        logger.debug(f"Added {role} message to session {session_id} (total: {len(self._histories[session_id])})")
    
    def clear_history(self, session_id: str = "default"):
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session identifier (default: "default")
        """
        if session_id in self._histories:
            del self._histories[session_id]
            self._save_all_histories()
            logger.info(f"Cleared history for session {session_id}")
    
    def clear_all_histories(self):
        """Clear all conversation histories."""
        self._histories = {}
        self._save_all_histories()
        logger.info("Cleared all conversation histories")

