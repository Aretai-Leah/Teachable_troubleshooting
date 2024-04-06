import os
from autogen.agentchat.assistant_agent import ConversableAgent
from autogen.agentchat.contrib.capabilities.agent_capability import AgentCapability
from autogen.agentchat.contrib.text_analyzer_agent import TextAnalyzerAgent
from autogen.agentchat.contrib.capabilities.teachability import Teachability
from autogen.agentchat.contrib.capabilities.teachability import MemoStore
from typing import Dict, Optional, Union, List, Tuple, Any
import chromadb
from chromadb.config import Settings
import chromadb
from chromadb.config import Settings

teachability = Teachability(
    verbosity=1,  # 0 for basic info, 1 to add memory operations, 2 for analyzer messages, 3 for memo lists.
    reset_db=False,  # Set to True to start with a fresh database.
    path_to_db_dir="./memories/teachability_db",
    recall_threshold=1.5,  # Higher numbers allow more (but less relevant) memos to be recalled.
)

memo_store = MemoStore(
    verbosity=1,
    reset=False,
    path_to_db_dir="./memories/teachability_db"
)

results = memo_store.list_memos()
print(results)