class DomainError(Exception):
    pass


class EntityNotFoundError(DomainError):
    pass


class EntityConflictError(DomainError):
    pass


class InvalidDomainValueError(DomainError):
    pass


class OperationFailedError(DomainError):
    pass
