class DeclarationError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field
