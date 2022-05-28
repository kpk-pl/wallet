from flaskr import db


def _getPipelineForUsedQuoteIds():
    pipeline = []
    pipeline.append({'$match': {
        'trashed': {'$ne': True}
    }})
    pipeline.append({'$project': {
        'quoteIds': {'$filter': {
            'input': {'$setUnion': [
                    ["$currency.quoteId", "$pricing.quoteId"],
                    {'$ifNull': [
                        {'$map': {
                            'input': "$pricing.interest",
                            'as': "pi",
                            'in': "$$pi.derived.quoteId"
                        }},
                        []
                    ]}
            ]},
            'as': "quoteId",
            'cond': { '$ne': ["$$quoteId", None] }
        }}
    }})
    pipeline.append({'$unwind': {
        'path': "$quoteIds",
        'preserveNullAndEmptyArrays': False
    }})
    pipeline.append({'$group': {
        '_id': None,
        'quoteIds': {'$addToSet': "$quoteIds"}
	}})
    return pipeline


def listIds(used=False):
    if used:
        assetInfo = list(db.get_db().assets.aggregate(_getPipelineForUsedQuoteIds()))
        return assetInfo[0]['quoteIds'] if assetInfo else []

    return []
