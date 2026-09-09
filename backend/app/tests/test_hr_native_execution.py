import base64
import hashlib
import importlib.util
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.extensions import db
from app.models import Document, Employee, SignatureRequest, SignatureEvent
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.native_signature_service import complete_recipient_fields, NativeSignatureError
from app.services.signature_input_service import normalize_signature_image


def image_data():
    img = Image.new("RGBA", (300, 100), "white")
    ImageDraw.Draw(img).line([(10, 60), (70, 20), (160, 80), (270, 25)], fill="black", width=4)
    output = BytesIO()
    img.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


@pytest.fixture()
def setup_execution(app, tenant, admin_user, tmp_path):
    app.config["SIGNATURE_EVIDENCE_STORAGE"] = "local"
    app.config["SIGNATURE_EVIDENCE_FOLDER"] = str(tmp_path / "evidence")
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    source = tmp_path / "contract.pdf"
    pdf = canvas.Canvas(str(source))
    pdf.drawString(70, 700, "Employment agreement")
    pdf.save()
    with app.app_context():
        user = register_user(
            {
                "tenant_id": tenant.id,
                "email": "signer@acme.test",
                "first_name": "Jane",
                "last_name": "Doe",
                "password": "StrongSignerPass123!",
                "roles": ["EMPLOYEE"],
                "email_verified_at": utcnow(),
            }
        )
        employee = Employee(
            tenant_id=tenant.id,
            user_id=user.id,
            employee_number="EMP-123",
            first_name="Jane",
            last_name="Doe",
            email=user.email,
            job_title="Engineer",
            hire_date=datetime.now().date(),
        )
        db.session.add(employee)
        db.session.flush()
        document = Document(
            tenant_id=tenant.id,
            employee_id=employee.id,
            title="Contract",
            document_type="contract",
            original_filename="contract.pdf",
            stored_filename="contract.pdf",
            file_path=str(source),
            mime_type="application/pdf",
            size_bytes=source.stat().st_size,
            checksum_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            access_level="employee",
        )
        db.session.add(document)
        db.session.commit()
        return {"document": str(document.id), "employee": str(employee.id), "source": source}


def placement(kind, **kwargs):
    return {"field_type": kind, "page_number": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05, **kwargs}


def create(client, headers, setup, **kwargs):
    return client.post(
        "/api/signature-requests",
        headers=headers,
        json={
            "document_id": setup["document"],
            "subject": "Please sign contract",
            "due_at": (datetime.now() + timedelta(days=7)).isoformat(),
            "recipients": [
                {
                    "employee_id": setup["employee"],
                    "role_label": "Employee",
                    "sequence": 1,
                    "fields": [
                        placement("signature"),
                        placement("date", y=0.3),
                        placement("text", y=0.4, label="Job title", prefill_key="employee.job_title", read_only=True),
                        placement("text", y=0.5, label="Employee ID", prefill_key="employee.employee_number"),
                    ],
                }
            ],
            **kwargs,
        },
    )


def login_signer(client):
    response = client.post("/api/auth/login", json={"email": "signer@acme.test", "password": "StrongSignerPass123!"})
    assert response.status_code == 200
    return {"X-CSRF-TOKEN": client.get_cookie("csrf_access_token").value}


def test_draft_prefills_signing_and_locked_employee_copy(app, client, auth_headers, setup_execution):
    response = create(client, auth_headers, setup_execution, save_as_draft=True)
    assert response.status_code == 201, response.json
    workflow = response.json["data"]
    recipient = workflow["recipients"][0]
    assert workflow["status"] == "draft" and workflow["sent_at"] is None
    assert recipient["status"] == "pending" and recipient["notified_at"] is None
    fields = {f["label"]: f for f in workflow["fields"]}
    assert fields["Job title"]["value"] == "Engineer"
    assert fields["Employee ID"]["value"] == "EMP-123"
    sent = client.post(f"/api/signature-requests/{workflow['id']}/send", headers=auth_headers)
    assert sent.status_code == 200, sent.json
    headers = login_signer(client)
    forbidden = client.post(
        f"/api/signature-requests/recipients/{recipient['id']}/submit",
        headers=headers,
        json={"consent": True, "fields": [{"field_id": fields["Job title"]["id"], "value": "CEO"}]},
    )
    assert forbidden.status_code == 400
    signed = client.post(
        f"/api/signature-requests/recipients/{recipient['id']}/submit",
        headers=headers,
        json={"consent": True, "signature_input": "uploaded", "signature_image": image_data()},
    )
    assert signed.status_code == 200, signed.json
    with app.app_context():
        executed = Document.query.filter(Document.executed_artifact_id.isnot(None)).one()
        assert str(executed.employee_id) == setup_execution["employee"]
        assert executed.file_path != str(setup_execution["source"])
        document_id = str(executed.id)
        events = SignatureEvent.query.filter_by(signature_request_id=workflow["id"]).all()
        signed_event = next(e for e in events if e.event_type == "signature.recipient_signed")
        assert signed_event.metadata_json["ip_address"] == "127.0.0.1"
        assert signed_event.metadata_json["email"] == "signer@acme.test"
        assert signed_event.metadata_json["version_id"] == workflow["id"]
        assert db.session.get(SignatureRequest, workflow["id"]).status == "completed"
    content = client.get(f"/api/documents/{document_id}/content")
    assert content.status_code == 200
    reader = PdfReader(BytesIO(content.data))
    assert reader.metadata["/KineticVersionID"] == workflow["id"]
    assert "/XObject" in reader.pages[0]["/Resources"]
    with app.app_context():
        executed = db.session.get(Document, document_id)
        Path(executed.file_path).write_bytes(b"tampered")
    assert client.get(f"/api/documents/{document_id}/content").status_code == 409


def test_templates_rebind_employee_and_detect_source_change(app, client, auth_headers, setup_execution):
    definition = {
        "subject": "Sign employment contract",
        "signing_mode": "sequential",
        "recipients": [
            {"role_label": "Employee", "sequence": 1, "fields": [placement("signature"), placement("date", y=0.3)]}
        ],
    }
    saved = client.post(
        "/api/signature-requests/templates",
        headers=auth_headers,
        json={
            "name": "Employment Contract - Kenya",
            "document_id": setup_execution["document"],
            "definition": definition,
        },
    )
    assert saved.status_code == 201, saved.json
    template_id = saved.json["data"]["id"]
    assert client.get("/api/signature-requests/templates").json["data"]["items"][0]["id"] == template_id
    used = client.post(
        f"/api/signature-requests/templates/{template_id}/instantiate",
        headers=auth_headers,
        json={"employee_id": setup_execution["employee"]},
    )
    assert used.status_code == 201, used.json
    assert used.json["data"]["document"]["id"] != setup_execution["document"]
    assert used.json["data"]["document"]["employee_id"] == setup_execution["employee"]
    setup_execution["source"].write_bytes(b"changed")
    refused = client.post(
        f"/api/signature-requests/templates/{template_id}/instantiate",
        headers=auth_headers,
        json={"employee_id": setup_execution["employee"]},
    )
    assert refused.status_code == 400
    invalid_employee = client.post(
        f"/api/signature-requests/templates/{template_id}/instantiate",
        headers=auth_headers,
        json={"employee_id": str(uuid4())},
    )
    assert invalid_employee.status_code == 400
    headers = login_signer(client)
    assert client.get("/api/signature-requests/templates", headers=headers).status_code == 403


def test_database_rejects_audit_update_and_delete(app, client, auth_headers, setup_execution):
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 201
    path = Path(__file__).parents[2] / "migrations/versions/035_hr_native_execution.py"
    spec = importlib.util.spec_from_file_location("retention_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with app.app_context():
        migration.install_retention(db.session.connection())
        db.session.commit()
        for statement in [
            "UPDATE signature_events SET description='forged'",
            "DELETE FROM signature_events",
            "UPDATE signature_artifacts SET checksum_sha256='forged'",
            "DELETE FROM signature_artifacts",
        ]:
            with pytest.raises(DatabaseError):
                db.session.execute(text(statement))
                db.session.commit()
            db.session.rollback()


def test_required_readonly_missing_prefill_rejected_before_send(app, client, auth_headers, setup_execution):
    with app.app_context():
        db.session.get(Employee, setup_execution["employee"]).job_title = None
        db.session.commit()
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 400
    with app.app_context():
        assert SignatureRequest.query.count() == 0


def test_signature_image_validation():
    assert base64.b64decode(normalize_signature_image(image_data())).startswith(b"\x89PNG")
    for value in ("data:image/svg+xml;base64,AAAA", "data:image/png;base64,invalid", "", None):
        with pytest.raises(ValueError):
            normalize_signature_image(value)
    out = BytesIO()
    Image.new("RGBA", (30, 30), (0, 0, 0, 0)).save(out, "PNG")
    with pytest.raises(ValueError, match="blank"):
        normalize_signature_image("data:image/png;base64," + base64.b64encode(out.getvalue()).decode())


def test_missing_required_submission_is_atomic():
    signature = SimpleNamespace(
        id=uuid4(), field_type="signature", value=None, required=True, label="Signature", completed_at=None
    )
    missing = SimpleNamespace(id=uuid4(), field_type="text", value=None, required=True, label="ID", completed_at=None)
    recipient = SimpleNamespace(fields=[signature, missing], name="Jane Doe")
    with pytest.raises(NativeSignatureError):
        complete_recipient_fields(recipient, utcnow(), "Jane Doe")
    assert signature.value is None and signature.completed_at is None


def test_word_preparation_preserves_original(app, client, auth_headers, setup_execution, monkeypatch):
    from app.services import document_conversion_service

    original_bytes = setup_execution["source"].read_bytes()
    monkeypatch.setattr(
        document_conversion_service,
        "convert_docx_to_pdf",
        lambda content: document_conversion_service.ConvertedPdf(content=original_bytes, page_count=1, engine="test"),
    )
    with app.app_context():
        document = db.session.get(Document, setup_execution["document"])
        document.original_filename = "contract.docx"
        document.mime_type = document_conversion_service.DOCX_MIME_TYPE
        db.session.commit()
    response = client.post(f"/api/documents/{setup_execution['document']}/prepare-signing", headers=auth_headers)
    assert response.status_code == 201, response.json
    assert response.json["data"]["id"] != setup_execution["document"]
    assert response.json["data"]["mime_type"] == "application/pdf"
    assert response.json["data"]["employee_id"] == setup_execution["employee"]
    assert setup_execution["source"].read_bytes() == original_bytes


def test_discard_draft_does_not_activate_signers(app, client, auth_headers, setup_execution):
    response = create(client, auth_headers, setup_execution, save_as_draft=True)
    workflow = response.json["data"]
    cancelled = client.patch(
        f"/api/signature-requests/{workflow['id']}/cancel",
        headers=auth_headers,
        json={"reason": "Needs further review"},
    )
    assert cancelled.status_code == 200, cancelled.json
    assert cancelled.json["data"]["status"] == "cancelled"
    assert all(r["notified_at"] is None for r in cancelled.json["data"]["recipients"])
