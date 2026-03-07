from ninja import Schema


class LoginSchema(Schema):
    idToken: str

class ProfileSchemaIn(Schema):
    skills_text: str
    intent_text: str


class UserSchemaIn(Schema):
    name:str
    