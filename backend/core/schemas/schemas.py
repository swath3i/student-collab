from ninja import Schema


class LoginSchema(Schema):
    idToken: str

class ProfileSchemaIn(Schema):
    skills_text: str
    intent_text: str


class UserSchemaIn(Schema):
    name:str
    
class ProfileCreateSchema(Schema):
    skills_text: str
    intent_text: str

class ConnectionRequestSchema(Schema):
    receiver_id: str


class ConnectionResponseSchema(Schema):
    accept: bool


class MessageSchemaIn(Schema):
    content: str