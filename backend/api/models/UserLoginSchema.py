from pydantic import BaseModel

class UserLoginSchema(BaseModel):
    userName:str
    userPassword:str