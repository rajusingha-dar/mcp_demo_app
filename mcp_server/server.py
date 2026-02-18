import json
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ── Init FastMCP ───────────────────────────────────────────────────────────────
mcp = FastMCP("personal-notes-server")

# ── Notes file path ────────────────────────────────────────────────────────────
NOTES_FILE = Path(__file__).parent / "notes.json"

# ── Helper: load notes from JSON ───────────────────────────────────────────────
# def load_notes() -> dict:
#     if not NOTES_FILE.exists():
#         return {}
#     with open(NOTES_FILE, "r") as f:
#         return json.load(f)


def load_notes() -> dict:
    if not NOTES_FILE.exists():
        save_notes({})
        return {}
    with open(NOTES_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)

# ── Helper: save notes to JSON ─────────────────────────────────────────────────
def save_notes(notes: dict) -> None:
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=2)

# ── Tool 1: Add a note ─────────────────────────────────────────────────────────
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new note with a title and content."""
    notes = load_notes()
    if title in notes:
        return f"⚠️ A note with title '{title}' already exists. Use a different title or delete the existing one first."
    notes[title] = content
    save_notes(notes)
    return f"✅ Note '{title}' saved successfully."

# ── Tool 2: List all notes ─────────────────────────────────────────────────────
@mcp.tool()
def list_notes() -> str:
    """List all available note titles."""
    notes = load_notes()
    if not notes:
        return "📭 No notes found. Start by adding a note!"
    titles = list(notes.keys())
    formatted = "\n".join(f"- {title}" for title in titles)
    return f"📋 You have {len(titles)} note(s):\n{formatted}"

# ── Tool 3: Read a note ────────────────────────────────────────────────────────
@mcp.tool()
def read_note(title: str) -> str:
    """Read the full content of a note by its title."""
    notes = load_notes()
    if title not in notes:
        available = ", ".join(notes.keys()) if notes else "none"
        return f"❌ Note '{title}' not found. Available notes: {available}"
    return f"📄 '{title}':\n{notes[title]}"

# ── Tool 4: Delete a note ──────────────────────────────────────────────────────
@mcp.tool()
def delete_note(title: str) -> str:
    """Delete a note by its title."""
    notes = load_notes()
    if title not in notes:
        available = ", ".join(notes.keys()) if notes else "none"
        return f"❌ Note '{title}' not found. Available notes: {available}"
    del notes[title]
    save_notes(notes)
    return f"🗑️ Note '{title}' deleted successfully."

# # ── Run server ─────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     mcp.run(transport="sse")


# With this
# if __name__ == "__main__":
#     mcp.run(transport="sse", host="0.0.0.0", port=8000)


# With this
import uvicorn

if __name__ == "__main__":
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)