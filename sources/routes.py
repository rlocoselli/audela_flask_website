from flask import Blueprint, request, jsonify
from .services import SourceService

sources_bp = Blueprint("sources", __name__)

@sources_bp.route("/", methods=["POST"])
def create_source():
    data = request.json
    source = SourceService.create_source(data)
    return jsonify({"id": source.id}), 201


@sources_bp.route("/<int:source_id>/fetch", methods=["GET"])
def fetch_source(source_id):
    data = SourceService.fetch_data(source_id)
    return jsonify(data)