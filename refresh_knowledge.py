"""
Script to refresh the VIT Mumbai official knowledge base by crawling
live information directly from https://vit.edu.in/.

Usage:
    python refresh_knowledge.py
"""

import sys
import logging
from rag_engine import kb_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    print("=" * 65)
    print("VIT Mumbai Knowledge Base Refresher")
    print("Target: https://vit.edu.in/")
    print("=" * 65)
    print(f"Current chunk count: {len(kb_engine.chunks)}")
    print("Fetching and re-indexing official pages. Please wait...")

    result = kb_engine.refresh()

    print("\nRefresh Results:")
    print(f"  Status:             {result.get('status')}")
    print(f"  Total Chunks:       {result.get('chunks_total')}")
    print(f"  New Chunks Added:   {result.get('new_chunks_added')}")
    print(f"  Timestamp:          {result.get('timestamp')}")

    if result.get("errors"):
        print("\nWarnings/Errors encountered:")
        for err in result["errors"]:
            print(f"  - {err}")
    else:
        print("\nAll official pages scraped and indexed successfully!")

    print("=" * 65)

if __name__ == "__main__":
    main()
