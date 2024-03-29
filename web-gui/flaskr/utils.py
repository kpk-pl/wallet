def simplifyModel(model):
    from decimal import Decimal
    from pydantic import BaseModel
    from enum import Enum

    if isinstance(model, list):
        return [simplifyModel(x) for x in model]
    elif isinstance(model, dict):
        return {key: simplifyModel(value) for key,value in model.items()}
    elif isinstance(model, BaseModel):
        return simplifyModel(model.dict())
    elif isinstance(model, Decimal):
        return str(model)
    elif isinstance(model, Enum):
        return model.value
    else:
        return model


def jsonify(obj):
    from flask import json
    from flask.json import JSONEncoder

    class JsonEncoder(JSONEncoder):
        def default(self, obj):
            from decimal import Decimal

            if isinstance(obj, Decimal):
               return str(obj)
            return JSONEncoder.default(self, obj)

    return json.dumps(obj, cls=JsonEncoder)


def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))
