import json
import os

from app import create_app
from app.services.demo_seed_service import seed_demo_data


environment = (
    os.getenv('APP_ENV')
    or os.getenv('FLASK_ENV')
    or 'development'
).lower()
app = create_app(environment)

with app.app_context():
    result = seed_demo_data()
    print(json.dumps(result, indent=2, sort_keys=True))
