from .models import ApiSource, db
from .api_client import ApiClient

class SourceService:

    @staticmethod
    def create_source(data):
        source = ApiSource(**data)
        db.session.add(source)
        db.session.commit()
        return source

    @staticmethod
    def fetch_data(source_id):
        source = ApiSource.query.get(source_id)
        if not source:
            raise ValueError("Source not found")
        return ApiClient.fetch(source)