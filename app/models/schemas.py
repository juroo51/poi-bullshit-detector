from pydantic import BaseModel, Field

from app.config import settings


class POICheckRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="POI name or category to check, e.g. 'groceries'",
    )
    lat: float = Field(
        ...,
        ge=settings.lat_min,
        le=settings.lat_max,
        description="Latitude in decimal degrees",
    )
    lon: float = Field(
        ...,
        ge=settings.lon_min,
        le=settings.lon_max,
        description="Longitude in decimal degrees",
    )


class POICheckResponse(BaseModel):
    suitable: bool = Field(..., description="Whether the name suits a POI at this location")
    reason: str = Field(..., description="Short explanation of the verdict")
    model: str | None = Field(None, description="Model that produced the judgment")
