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
    # O gato certo esteve na area, mas nao comeu, bebeu nem usou a caixa.
    NO_ACTION = "NO_ACTION"
    # Mais de um gato no quadro: a visita vale, a identificacao individual nao.
    MULTIPLE_PETS = "MULTIPLE_PETS"


class HouseholdSpecies(StrEnum):
    CAT = "CAT"
    DOG = "DOG"
    BOTH = "BOTH"


class PetSpecies(StrEnum):
    CAT = "CAT"
    DOG = "DOG"
