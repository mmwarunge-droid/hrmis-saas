from flask import request


def get_pagination(default_per_page=20, max_per_page=100):
    page = max(int(request.args.get('page', 1)), 1)
    per_page = min(max(int(request.args.get('per_page', default_per_page)), 1), max_per_page)
    return page, per_page


def paginated_response(pagination):
    return {
        'items': [item.to_dict() for item in pagination.items],
        'meta': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        },
    }
