"""Same items/next_cursor and base64(timestamp|id) format as orders (task 1.3).

Page size is 1..100, default 50. Execution ids retain Alpaca's text identifier;
report ids are UUIDs. No pagination details are exposed in the HTTP contract.
"""

from typing import Annotated

from fastapi import Query

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import Output

PageSize = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=2048)]


class PageResponse[T](Output):
    items: list[T]
    next_cursor: str | None
