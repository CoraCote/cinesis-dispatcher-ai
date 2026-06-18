"""Pydantic data models for the Cinesis Good Fit Test."""

from typing import Optional
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float
    lon: float
    city: str
    state: str

    def __str__(self) -> str:
        return f"{self.city}, {self.state}"


class DriverProfile(BaseModel):
    name: str
    current_location: Coordinates
    home_base: Coordinates
    equipment_type: str = Field(description="e.g. Dry Van, Reefer, Flatbed")
    trailer_length_ft: int
    max_weight_lbs: int
    available_date: str = Field(description="ISO YYYY-MM-DD")
    min_effective_rate_per_mile: float = Field(
        description="All-in effective rate floor in $/mile"
    )
    preferred_regions: list[str]
    hazmat_certified: bool
    team_driver: bool
    notes: str = Field(
        description="Implied constraints, interpretations, and anything that did not fit a structured field"
    )


class Load(BaseModel):
    load_id: str
    trailer_type: str
    origin: Coordinates
    destination: Optional[Coordinates]
    weight_lbs: int
    price: Optional[float]
    notes: str = ""


class RankedLoad(BaseModel):
    load: Load
    deadhead_to_origin_miles: float
    loaded_miles: float
    deadhead_home_miles: float
    total_miles: float
    effective_rate_per_mile: float
    rank: int
