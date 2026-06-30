from dataclasses import dataclass
from uuid import UUID


@dataclass
class MemoryResult:
    text: str
    dataset_name: str
    source: str
    score: float | None = None


async def memory_search(query: str, employee_id: UUID) -> list[MemoryResult]:
    """Mock memory search. Replace with Cognee memory SDK retrieval in future phases."""
    return []


async def memory_ingest(content: str, employee_id: UUID) -> bool:
    """Mock memory ingest. Replace with Cognee memory SDK indexing in future phases."""
    return True
