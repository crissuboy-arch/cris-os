"""
Caracterização (Onda 1 / B0) — SQLiteMemory e SQLiteOpsStore.
Fixa o comportamento atual antes da base SQLite comum (N3/B2).
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.domain.events import Event  # noqa: E402
from core.models import KnowledgeItem, Task  # noqa: E402
from storage import SQLiteMemory, SQLiteOpsStore  # noqa: E402


def test_memory_conversation_and_permanent(tmp_path: Path):
    m = SQLiteMemory(tmp_path / "m.db")
    m.add_message("s", "user", "oi")
    m.add_message("s", "assistant", "olá")
    assert m.recent_messages("s", 10) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
    ]
    m.remember_permanent(KnowledgeItem(type="t", title="T", content="C"))
    assert m.count_permanent() == 1
    assert [k.title for k in m.recall_permanent()] == ["T"]
    m.close()


def test_ops_eventlog_tasks_lease(tmp_path: Path):
    ops = SQLiteOpsStore(tmp_path / "o.db")
    seq = ops.append(Event(type="x.y", payload={"a": 1}, correlation_id="c"))
    assert seq >= 1
    lidos = ops.read_since(0)
    assert lidos and lidos[0][1].type == "x.y"

    t = Task(agent="a", instruction="do")
    ops.save(t)
    assert ops.get(t.id).agent == "a"

    assert ops.acquire("nodeA", 60) is True
    assert ops.acquire("nodeB", 60) is False
    ops.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        base = Path(d)
        for i, t in enumerate((test_memory_conversation_and_permanent,
                               test_ops_eventlog_tasks_lease)):
            sub = base / f"t{i}"
            sub.mkdir()
            t(sub)
    print("OK - test_storage")
