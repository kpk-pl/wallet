def simplifyModel(model):
    from decimal import Decimal
    from pydantic import BaseModel

    if isinstance(model, list):
        return [simplifyModel(x) for x in model]
    elif isinstance(model, dict):
        return {key: simplifyModel(value) for key,value in model.items()}
    elif isinstance(model, BaseModel):
        return simplifyModel(model.dict())
    elif isinstance(model, Decimal):
        return str(model)
    else:
        return model

