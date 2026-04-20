from pathlib import Path

from flask import Blueprint, Response, current_app, g, jsonify, request, send_from_directory, url_for

from app.services.auth_service import auth_required
from app.services.storage_service import download_supabase_object, save_supabase_upload, storage_backend
from app.services.upload_service import save_upload

bp = Blueprint("upload", __name__)


@bp.post("/upload")
@auth_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Arquivo nao enviado."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Arquivo invalido."}), 400

    vehicle = request.form.get("vehicle", "veiculo")
    item = request.form.get("item", "item")
    module = request.form.get("module")
    photo_type = request.form.get("tipo_foto") or request.form.get("photo_type")
    user = request.form.get("user", g.current_user.login)
    item_context = "_".join(part for part in (photo_type, module, item) if part)

    try:
        if storage_backend() == "supabase":
            object_path = save_supabase_upload(file, vehicle, item_context, user)
            return jsonify(
                {
                    "filename": Path(object_path).name,
                    "path": f"/uploads/supabase/{object_path}",
                    "url": url_for("upload.get_supabase_file", object_path=object_path, _external=True),
                    "storage": "supabase",
                }
            ), 201

        filename = save_upload(file, Path(current_app.config["UPLOAD_FOLDER"]), vehicle, item_context, user)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(
        {
            "filename": filename,
            "path": f"/uploads/{filename}",
            "url": url_for("upload.get_uploaded_file", filename=filename, _external=True),
            "storage": "local",
        }
    ), 201


@bp.get("/uploads/supabase/<path:object_path>")
def get_supabase_file(object_path: str):
    try:
        content, content_type = download_supabase_object(object_path)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo nao encontrado."}), 404
    return Response(content, mimetype=content_type)


@bp.get("/uploads/<path:filename>")
def get_uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
