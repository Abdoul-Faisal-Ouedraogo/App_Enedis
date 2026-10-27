from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# Creating Enums for categorical fields and automating value assignment and error handling.
class BuildingType(str, Enum):
    maison = "maison"
    appartement = "appartement"
    immeuble = "immeuble"


class HeatingType(str, Enum):
    electricite = "Électricité"
    gaz = "Gaz naturel"
    autre = "Autre"


# -------------------------------- Main Model for the input data, error and type handling included -------------------------------- #
class InputData(BaseModel):
    city: str = Field(
        ..., description="Location must be a city name or an INSEE code (as string)"
    )
    cost: Optional[float] = Field(
        None,
        gt=0,
        description="Cost must be a positive value if provided. If not, regression model will be used to predict the cost.",
    )
    area: float = Field(..., gt=0, description="Area must be a positive value.")
    n_floors: int = Field(
        ..., gt=0, description="Number of floors must be a positive value."
    )
    age: int = Field(..., gt=0, description="Age must be a positive value.")
    main_heating_energy: HeatingType = Field(
        ..., description="Main heating energy type."
    )
    building: BuildingType = Field(..., description="Building type.")
