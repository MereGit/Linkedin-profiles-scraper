from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from enum import Enum
from typing import Optional


class ResultStatus(str, Enum):
    TOTAL_MATCH = "match_"
    NOT_MATCH = "Not matched"


@dataclass(frozen=True, slots=True)
class PersonResult:
    name: str
    firm: str
    linkedin_url: Optional[str] = None
    status: ResultStatus = ResultStatus.NOT_MATCH

    def to_row(self) -> dict:
        """
        Convert to a CSV-safe dict row.
        - Enums -> string
        - None -> ""
        """
        d = asdict(self)
        d["status"] = self.status.value
        for k, v in d.items():
            if v is None:
                d[k] = ""
        return d
