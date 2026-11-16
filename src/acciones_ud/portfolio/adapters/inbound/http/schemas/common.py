from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, WithJsonSchema

DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda value: str(value), return_type=str),
    WithJsonSchema({"type": "string", "format": "decimal"}),
]


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, allow_inf_nan=False)
