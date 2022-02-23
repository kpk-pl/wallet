from flaskr.model import AssetOperation
from pydantic import BaseModel
from typing import List


class DecoratedAssetOperation(AssetOperation):
    pass


class Operations(object):
    def __init__(self):
        super(Operations, self).__init__();

    def __call__(self, operations):
        result = [DecoratedAssetOperation(**o) for o in operations]
        return result
