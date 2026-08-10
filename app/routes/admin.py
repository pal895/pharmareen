from __future__ import annotations

from typing import Any
import base64
import os
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.branding import APP_BRAND
from app.access_control import require_admin_actor
from app.config import get_settings
from app.services.pharmacy_onboarding import PharmacyOnboardingService, PharmacyPayload
from app.owner_auth import owner_auth_service


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_actor)],
)


class PharmacyCreateRequest(BaseModel):
    pharmacy_name: str
    owner_name: str = ""
    phone: str = ""
    location: str = ""
    notes: str = ""


class BulkCreateRequest(BaseModel):
    pharmacies: list[PharmacyCreateRequest]


@router.get("/onboard", response_class=HTMLResponse)
def onboard_page() -> str:
    return ADMIN_HTML.replace("__APP_BRAND__", APP_BRAND)


@router.post("/create-pharmacy")
def create_pharmacy(payload: PharmacyCreateRequest) -> dict[str, Any]:
    try:
        return service().create_pharmacy(to_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/create-pharmacies-bulk")
def create_pharmacies_bulk(payload: BulkCreateRequest) -> dict[str, Any]:
    records = [to_payload(item) for item in payload.pharmacies]
    return service().create_pharmacies_bulk(records)


@router.get("/pharmacies")
def list_pharmacies() -> dict[str, Any]:
    records = service().list_pharmacies()
    return {"ok": True, "pharmacies": records}


@router.get("/pharmacy/{pharmacy_id}")
def get_pharmacy(pharmacy_id: str) -> dict[str, Any]:
    record = service().get_pharmacy(pharmacy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return {"ok": True, "pharmacy": record}


@router.post("/pharmacy/{pharmacy_id}/owner-activation")
def create_owner_activation(pharmacy_id: str, request: Request) -> dict[str, Any]:
    allowed_pharmacy = os.getenv("PHARMAREEN_OWNER_ACTIVATION_PHARMACY_ID", "").strip()
    if allowed_pharmacy and pharmacy_id != allowed_pharmacy:
        raise HTTPException(status_code=403, detail="Owner activation is restricted to the staging test pharmacy.")
    record = service().get_pharmacy(pharmacy_id)
    if not record or str(record.get("active") or "").lower() in {"no", "false", "0", "inactive"}:
        raise HTTPException(status_code=404, detail="Active pharmacy owner not found")
    raw_token, invitation = owner_auth_service.create_activation(record)
    activation_url = f"{str(request.base_url).rstrip('/')}/main-app/activate#token={raw_token}"
    try:
        import qrcode
        image = qrcode.make(activation_url)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        qr_data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Local QR generation is unavailable") from exc
    return {"ok": True, "pharmacy_id": invitation.pharmacy_id, "pharmacy_name": invitation.pharmacy_name, "owner_name": invitation.owner_name, "expires_in": owner_auth_service.activation_ttl_seconds, "activation_url": activation_url, "qr_data_uri": qr_data_uri}


@router.post("/pharmacy/{pharmacy_id}/legacy-recovery-enrollment")
def enroll_legacy_recovery(pharmacy_id: str, request: Request) -> dict[str, Any]:
    """One-time recovery enrollment for an explicitly allowlisted partial tenant."""
    allowed_pharmacy = os.getenv("MS20_RECOVERY_MIGRATION_PHARMACY_ID", "").strip()
    allowed_owner = os.getenv("MS20_RECOVERY_MIGRATION_OWNER_ID", "").strip()
    if not allowed_pharmacy or pharmacy_id != allowed_pharmacy:
        raise HTTPException(status_code=403, detail="Recovery migration is not enabled for this pharmacy.")
    record = service().get_pharmacy(pharmacy_id)
    if not record or str(record.get("owner_id") or "") != allowed_owner:
        raise HTTPException(status_code=403, detail="Recovery migration identity does not match.")
    if owner_auth_service.recovery_is_enrolled(pharmacy_id=pharmacy_id, owner_id=allowed_owner):
        raise HTTPException(status_code=409, detail="Recovery is already enrolled; migration is permanently closed.")
    recovery_key = owner_auth_service.enroll_recovery_key(pharmacy_id=pharmacy_id, owner_id=allowed_owner)
    return {
        "ok": True, "pharmacy_id": pharmacy_id, "recovery_key": recovery_key,
        "recovery_url": f"{str(request.base_url).rstrip('/')}/main-app/recover?pharmacy_id={pharmacy_id}",
        "one_time_enrollment": True,
    }


@router.post("/photo-onboard-placeholder")
def photo_onboard_placeholder() -> dict[str, Any]:
    # Future flow: photo upload -> OpenAI Vision extraction -> review table -> create/update Inventory.
    return {"ok": True, "message": "Photo onboarding placeholder ready for Phase 5"}


def service() -> PharmacyOnboardingService:
    return PharmacyOnboardingService(get_settings())


def to_payload(payload: PharmacyCreateRequest) -> PharmacyPayload:
    return PharmacyPayload(
        pharmacy_name=payload.pharmacy_name,
        owner_name=payload.owner_name,
        phone=payload.phone,
        location=payload.location,
        notes=payload.notes,
    )


ADMIN_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__APP_BRAND__ Pharmacy Onboarding</title>
  <style>
    body { margin:0; font-family: Arial, sans-serif; background:#f6f8fb; color:#172033; }
    main { max-width: 1040px; margin: 0 auto; padding: 28px 16px 48px; }
    h1 { margin: 0 0 18px; font-size: 28px; }
    section { background:#fff; border:1px solid #d9e1ec; border-radius:8px; padding:18px; margin:16px 0; }
    label { display:block; margin:10px 0 5px; font-weight:700; }
    input, textarea { width:100%; box-sizing:border-box; padding:10px; border:1px solid #b8c4d6; border-radius:6px; font-size:15px; }
    textarea { min-height: 120px; font-family: Consolas, monospace; }
    button { margin-top:12px; padding:10px 14px; border:0; border-radius:6px; background:#126c43; color:#fff; font-weight:700; cursor:pointer; }
    button.secondary { background:#244263; }
    table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    th, td { border-bottom:1px solid #e3e8f1; padding:8px; text-align:left; vertical-align:top; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; }
    .log { white-space:pre-wrap; background:#0e1726; color:#d8f5e5; padding:12px; border-radius:6px; overflow:auto; }
    @media (max-width:700px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>__APP_BRAND__ Pharmacy Onboarding</h1>

  <section>
    <h2>Create One Pharmacy</h2>
    <div class="grid">
      <div><label>Pharmacy name</label><input id="pharmacy_name"></div>
      <div><label>Owner name</label><input id="owner_name"></div>
      <div><label>Phone number</label><input id="phone"></div>
      <div><label>Location</label><input id="location"></div>
    </div>
    <label>Notes</label><input id="notes">
    <button onclick="createOne()">Create Pharmacy</button>
  </section>

  <section>
    <h2>Bulk Create Pharmacies</h2>
    <textarea id="bulk" placeholder="ABC Pharmacy, Mary, 0712345678, Nairobi"></textarea>
    <button onclick="createBulk()">Create All</button>
  </section>

  <section>
    <h2>Existing Pharmacies</h2>
    <button class="secondary" onclick="loadPharmacies()">Refresh Pharmacy List</button>
    <div id="pharmacies"></div>
  </section>

  <section id="activation" style="display:none">
    <h2>One-time Owner Activation</h2><p id="activationIdentity"></p><img id="activationQr" alt="Owner activation QR" width="260" height="260"><button class="secondary" onclick="copyActivation()">Copy activation link</button><p>Expires in 15 minutes and can be used once. Do not screenshot or share the QR.</p>
  </section>

  <section>
    <h2>Result Log</h2>
    <div id="log" class="log">Ready.</div>
  </section>
</main>
<script>
const logBox = document.getElementById('log');
let activationLink = '';
function log(value) { logBox.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
function rowToPharmacy(line) {
  const parts = line.split(',').map(x => x.trim());
  return { pharmacy_name: parts[0] || '', owner_name: parts[1] || '', phone: parts[2] || '', location: parts[3] || '' };
}
async function createOne() {
  const payload = {
    pharmacy_name: document.getElementById('pharmacy_name').value,
    owner_name: document.getElementById('owner_name').value,
    phone: document.getElementById('phone').value,
    location: document.getElementById('location').value,
    notes: document.getElementById('notes').value
  };
  const res = await fetch('/admin/create-pharmacy', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  const data = await res.json();
  log(data); loadPharmacies();
}
async function createBulk() {
  const pharmacies = document.getElementById('bulk').value.split('\\n').map(x => x.trim()).filter(Boolean).map(rowToPharmacy);
  const res = await fetch('/admin/create-pharmacies-bulk', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pharmacies}) });
  const data = await res.json();
  log(data); loadPharmacies();
}
async function loadPharmacies() {
  const res = await fetch('/admin/pharmacies');
  const data = await res.json();
  const rows = (data.pharmacies || []).map(p => `<tr><td>${p.pharmacy_name || ''}</td><td>${p.pharmacy_id || ''}</td><td>${p.phone || ''}</td><td><a href="${p.spreadsheet_url || '#'}" target="_blank">${p.spreadsheet_id || ''}</a></td><td>${p.status || ''}</td><td><button onclick="createActivation('${p.pharmacy_id || ''}')">Owner QR</button></td></tr>`).join('');
  document.getElementById('pharmacies').innerHTML = `<table><thead><tr><th>Pharmacy</th><th>ID</th><th>Phone</th><th>Spreadsheet</th><th>Status</th><th>Owner access</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function createActivation(pharmacyId){const res=await fetch(`/admin/pharmacy/${encodeURIComponent(pharmacyId)}/owner-activation`,{method:'POST'});const data=await res.json();if(!res.ok){log({ok:false,message:data.detail||'Activation unavailable'});return;}activationLink=data.activation_url;document.getElementById('activationIdentity').textContent=`${data.pharmacy_name} — ${data.owner_name}`;document.getElementById('activationQr').src=data.qr_data_uri;document.getElementById('activation').style.display='block';log('One-time owner activation created safely.');}
async function copyActivation(){await navigator.clipboard.writeText(activationLink);log('Activation link copied. Keep it private and use it once.');}
loadPharmacies();
</script>
</body>
</html>
"""
