"""Global library of image templates for WAIT_UNTIL image conditions.

Templates are stored once in the ``templates`` table (base64 PNG) and referenced
by id from any number of steps, so the same image can be reused across tasks and
profiles. Unlike variables, the library is *not* scoped to a profile.
"""
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .database_manager import DatabaseManager


@dataclass
class TemplateEntry:
    id: int
    name: str
    image_b64: str


class TemplateStore(QObject):
    """CRUD over the global template library, cached in memory."""
    templateAdded = Signal(object)    # TemplateEntry
    templateRemoved = Signal(int)     # id
    templateRenamed = Signal(int, str)  # id, name

    def __init__(self, db: "DatabaseManager", parent=None):
        super().__init__(parent)
        self.db = db
        self._entries: dict[int, TemplateEntry] = {}

    def load(self):
        """(Re)load every template into memory, newest first."""
        self._entries.clear()
        with self.db.getConn() as conn:
            rows = conn.execute(
                "SELECT id, name, image FROM templates ORDER BY created_at DESC, id DESC"
            ).fetchall()
        for row in rows:
            self._entries[row["id"]] = TemplateEntry(row["id"], row["name"] or "", row["image"])

    def all(self) -> list[TemplateEntry]:
        return list(self._entries.values())

    def get(self, template_id: int) -> TemplateEntry | None:
        return self._entries.get(template_id)

    def getB64(self, template_id: int) -> str | None:
        entry = self._entries.get(template_id)
        return entry.image_b64 if entry else None

    def add(self, image_b64: str, name: str | None = None) -> TemplateEntry:
        """Insert a template, or return the existing entry if identical bytes are already stored."""
        for entry in self._entries.values():
            if entry.image_b64 == image_b64:
                return entry  # dedupe: identical image already in the library

        with self.db.getConn() as conn:
            cur = conn.execute(
                "INSERT INTO templates (name, image) VALUES (?, ?)", (name, image_b64))
            new_id = cur.lastrowid
            if not name:
                # Name from the unique row id so defaults never collide after deletions.
                name = f"Template {new_id}"
                conn.execute("UPDATE templates SET name = ? WHERE id = ?", (name, new_id))
            conn.commit()

        entry = TemplateEntry(new_id, name, image_b64)
        # Keep newest-first ordering to match load().
        self._entries = {new_id: entry, **self._entries}
        self.templateAdded.emit(entry)
        return entry

    def rename(self, template_id: int, name: str):
        entry = self._entries.get(template_id)
        if entry is None or name == entry.name:
            return
        with self.db.getConn() as conn:
            conn.execute("UPDATE templates SET name = ? WHERE id = ?", (name, template_id))
            conn.commit()
        entry.name = name
        self.templateRenamed.emit(template_id, name)

    def delete(self, template_id: int):
        if template_id not in self._entries:
            return
        with self.db.getConn() as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            conn.commit()
        del self._entries[template_id]
        self.templateRemoved.emit(template_id)
