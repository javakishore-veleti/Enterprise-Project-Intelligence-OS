"""A tiny in-memory Mongo fake supporting the operators the tools use.

Supports equality + ``$in`` / ``$nin`` / ``$ne`` / ``$gte`` / ``$lte`` filters, a
``find`` cursor with ``.sort().limit()``, ``find_one`` (with ``sort``),
``count_documents``, and ``distinct``. It is a ``MongoDatabaseFactory`` stand-in:
``.db()[collection]`` returns a collection.
"""
from __future__ import annotations

from typing import Any


def _match(doc: dict, flt: dict) -> bool:
    for key, cond in flt.items():
        value = doc.get(key)
        if isinstance(cond, dict):
            for op, operand in cond.items():
                if op == "$in" and value not in operand:
                    return False
                if op == "$nin" and value in operand:
                    return False
                if op == "$ne" and value == operand:
                    return False
                if op == "$gte" and (value is None or value < operand):
                    return False
                if op == "$lte" and (value is None or value > operand):
                    return False
        elif value != cond:
            return False
    return True


def _strip(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


class _Cursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def sort(self, field: str, direction: int = 1) -> "_Cursor":
        self._docs = sorted(
            self._docs,
            key=lambda d: (d.get(field) is None, d.get(field)),
            reverse=direction < 0,
        )
        return self

    def limit(self, n: int) -> "_Cursor":
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _Collection:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = [dict(d) for d in docs]

    def find(self, flt: dict | None = None, projection: dict | None = None) -> _Cursor:
        flt = flt or {}
        return _Cursor([_strip(d) for d in self._docs if _match(d, flt)])

    def find_one(self, flt: dict | None = None, projection: dict | None = None,
                 sort: list | None = None) -> dict | None:
        flt = flt or {}
        docs = [d for d in self._docs if _match(d, flt)]
        if sort:
            for field, direction in reversed(sort):
                docs = sorted(docs, key=lambda d: (d.get(field) is None, d.get(field)),
                              reverse=direction < 0)
        return _strip(docs[0]) if docs else None

    def count_documents(self, flt: dict | None = None) -> int:
        flt = flt or {}
        return sum(1 for d in self._docs if _match(d, flt))

    def distinct(self, field: str, flt: dict | None = None) -> list:
        flt = flt or {}
        out: list = []
        for d in self._docs:
            if _match(d, flt):
                v = d.get(field)
                if v is not None and v not in out:
                    out.append(v)
        return out


class FakeDb:
    def __init__(self, collections: dict[str, list[dict]]) -> None:
        self._c = {name: _Collection(docs) for name, docs in collections.items()}

    def __getitem__(self, name: str) -> _Collection:
        return self._c.get(name) or _Collection([])


class FakeMongo:
    """A ``MongoDatabaseFactory`` stand-in over in-memory collections."""

    def __init__(self, collections: dict[str, list[dict]]) -> None:
        self._db = FakeDb(collections)

    def db(self) -> FakeDb:
        return self._db
