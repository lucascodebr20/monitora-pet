from enum import StrEnum


class ZoneType(StrEnum):
    FOOD = "FOOD"
    WATER = "WATER"
    LITTER = "LITTER"
    CUSTOM = "CUSTOM"


class Activity(StrEnum):
    DRINKING = "DRINKING"
    EATING = "EATING"
    USING_LITTER = "USING_LITTER"
    NEAR_ZONE = "NEAR_ZONE"
    UNCERTAIN = "UNCERTAIN"


class ReviewDecision(StrEnum):
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    INCONCLUSIVE = "INCONCLUSIVE"


class PetSpecies(StrEnum):
    CAT = "CAT"
    DOG = "DOG"
