from typing import TYPE_CHECKING, Hashable
from PySide6.QtCore import Signal, QObject

from .variable_config import VariableConfig
from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.registries.capture_type_registry import GlobalCaptureRegistry

if TYPE_CHECKING:
    from .database_manager import DatabaseManager


def copyVarsToNewProfile(cursor, old_profile_id, new_profile_id):
    cursor.execute("""
                   INSERT INTO variables (profile_id, key, value, data_type, hint)
                   SELECT ?, key, value, data_type, hint
                   FROM variables
                   WHERE profile_id = ?
                   """, (new_profile_id, old_profile_id))


class VariableStore(QObject):
    """Variables are localized to the profile"""
    varAdded = Signal(str, object) # (key string, config)
    varRemoved = Signal(str, object) # (key string, config)
    varChanged = Signal(str) # (key string)

    def __init__(self, db: "DatabaseManager", parent=None):
        super().__init__(parent)
        self.db = db
        self._profile_id: int | None = None
        self._vars: dict[str, VariableConfig] = {}
        self._pending_vars: dict[str, dict] = {} # Vars added before the db loads

    def add(self, key: Hashable, data_type: CaptureMode | type, default_val: object=None, pick_hint: str=None):
        """
        Add a variable to the store AND immediately upserts to DB.

        If the key is present already and value types differ, overwrites the previous variable.
        Args:
            key: The key to store the variable under.
            data_type: The value type of the variable.
            default_val: The default value of this variable.
            pick_hint: The hint to display while the variable is being picked or hovered over
        """
        key_str = VariableConfig.keyToStr(key)

        # Variable added before loading, add to pending
        if self._profile_id is None:
            self._pending_vars[key_str] = {
                'key': key,
                'data_type': data_type,
                'default_val': default_val,
                'pick_hint': pick_hint
            }
            return

        if key_str not in self:
            config = VariableConfig(data_type, default_val, pick_hint)
            self._vars[key_str] = config
            self._sql_upsert(key_str, config)
            self.varAdded.emit(key_str, config)
        else:
            config = self[key_str]
            has_changes = False
            if config.hint != pick_hint and pick_hint is not None:
                config.hint = pick_hint
                has_changes = True

            actual_type = GlobalCaptureRegistry.get(data_type).type_class if GlobalCaptureRegistry.containsMode(data_type) else data_type

            # If value types differ, or there's no value for config, overwrite the previous value and value type
            if (actual_type is not config.data_type) or (config.value is None and default_val != config.value):
                has_changes = True
                config.data_type = actual_type
                config.value = default_val

            if has_changes:
                self._sql_upsert(key_str, config)
                self.varChanged.emit(key_str)

    def remove(self, key: Hashable) -> VariableConfig | None:
        """Attempts to remove the key from the store. If the key is not present, returns None."""
        key_str = VariableConfig.keyToStr(key)
        if key_str in self:
            config = self._vars.pop(key_str)
            with self.db.getConn() as conn:
                conn.execute("DELETE FROM variables WHERE profile_id = ? AND key = ?",
                             (self._profile_id, key_str))
                conn.commit()

            self.varRemoved.emit(key_str, config)
            return config
        return None

    def updateValue(self, key: Hashable, new_value):
        """
        Updates the value for the config associated with the key to be the new value.

        Args:
            key: The key to store the variable under.
            new_value: The new value.

        Raises:
            KeyError: If the key is not present in the store.
        """
        key_str = VariableConfig.keyToStr(key)

        if not key_str in self: raise KeyError(f"Could not find key '{key_str}' in store.")
        config = self._vars[key_str]
        config.value = new_value
        val_str = config.valToStr()
        with self.db.getConn() as conn:
            conn.execute("UPDATE variables SET value = ? WHERE profile_id = ? AND key = ?",
                         (val_str, self._profile_id, key_str))
            conn.commit()

        self.varChanged.emit(key_str)

    def _sql_upsert(self, key, config):
        """Helper to insert or replace a record."""
        type_str = config.data_type.__name__
        val_str = config.valToStr()
        with self.db.getConn() as conn:
            conn.execute("""
                         INSERT INTO variables (profile_id, key, value, data_type, hint)
                         VALUES (?, ?, ?, ?, ?)
                         ON CONFLICT(profile_id, key) DO UPDATE SET value=excluded.value,
                                                                    data_type=excluded.data_type,
                                                                    hint=excluded.hint
                         """, (self._profile_id, key, val_str, type_str, config.hint))
            conn.commit()

    def get(self, key: Hashable) -> VariableConfig | None:
        return self._vars.get(VariableConfig.keyToStr(key))

    def items(self):
        return self._vars.items()

    def values(self):
        return self._vars.values()

    def keys(self):
        return self._vars.keys()

    def load(self, profile_id: int):
        self._profile_id = profile_id
        self._vars.clear()

        # Process pending variables first and place them into memory
        for key_str, var_data in self._pending_vars.items():
            dt = var_data['data_type']
            actual_type = GlobalCaptureRegistry.get(dt).type_class if GlobalCaptureRegistry.containsMode(dt) else dt
            config = VariableConfig(actual_type, var_data['default_val'], var_data['pick_hint'])
            self._vars[key_str] = config

        db_updates = []
        db_inserts = []

        with self.db.getConn() as conn:
            rows = conn.execute("SELECT * FROM variables WHERE profile_id = ?", (profile_id,)).fetchall()
            db_keys = set()

            # Reconcile DB variables against pending variables
            for row in rows:
                row_key = row["key"]
                db_keys.add(row_key)

                if row_key in self._vars:
                    # Pending var also exists in DB
                    pending_config = self._vars[row_key]
                    db_config = VariableConfig.fromRow(row)

                    if pending_config.data_type is db_config.data_type:
                        # Types match: update the memory config to use the DB's saved value
                        pending_config.value = db_config.value
                    else:
                        # Types mismatch: prepare to overwrite DB with the new pending type & value
                        db_updates.append((
                            pending_config.valToStr(),
                            pending_config.data_type.__name__,
                            pending_config.hint,
                            profile_id,
                            row_key
                        ))
                else:
                    # Not in pending, just load directly from DB into memory
                    self._vars[row_key] = VariableConfig.fromRow(row)

            # Find pending variables that weren't in the DB at all (newly coded variables)
            for key_str, config in self._vars.items():
                if key_str in self._pending_vars and key_str not in db_keys:
                    db_inserts.append((
                        profile_id,
                        key_str,
                        config.valToStr(),
                        config.data_type.__name__,
                        config.hint
                    ))

            # Execute all batch operations at once for $O(1)$ DB latency
            if db_updates:
                conn.executemany("""
                                 UPDATE variables
                                 SET value = ?, data_type = ?, hint = ?
                                 WHERE profile_id = ? AND key = ?
                                 """, db_updates)

            if db_inserts:
                conn.executemany("""
                                 INSERT INTO variables (profile_id, key, value, data_type, hint)
                                 VALUES (?, ?, ?, ?, ?)
                                 """, db_inserts)

            conn.commit()

        # Clear pending queue after flush
        self._pending_vars.clear()

    def __contains__(self, item):
        return item in self._vars

    def __getitem__(self, item):
        return self._vars[item]

    def __len__(self):
        return len(self._vars)

    def __iter__(self):
        return iter(self._vars)