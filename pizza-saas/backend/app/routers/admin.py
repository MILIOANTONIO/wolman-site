"""
Pannello admin: revisione KYC, inserimento manuale numero DIDWW e credenziali
WhatsApp (passi manuali per l'MVP, vedi punto 6/7 del piano), approvazione
finale che crea l'agente ElevenLabs e attiva il tenant.
"""
import os
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_admin
from app.db import get_db
from app.models import AdminUser, CreditTransaction, DidwwRegulatoryProfile, KycDocument, Order, PhoneNumber, Tenant, TenantSettings, User, WhatsappChannel
from app.routers.onboarding import UPLOADS_DIR
from app.services import billing, didww_client
from app.services.crypto import encrypt_token
from app.services.elevenlabs_agents import create_agent, update_agent
from app.services.prompt_builder import build_agent_prompt
from app.services.resend_email import build_activation_email, send_email

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    status_counts = dict(
        (await db.execute(select(Tenant.status, func.count()).group_by(Tenant.status))).all()
    )
    total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    total_revenue_cents = (
        await db.execute(select(func.coalesce(func.sum(CreditTransaction.amount_cents), 0)).where(CreditTransaction.type == "topup"))
    ).scalar_one()
    total_charged_cents = (
        await db.execute(
            select(func.coalesce(func.sum(-CreditTransaction.amount_cents), 0)).where(CreditTransaction.type.in_(["plan_charge", "overage_charge"]))
        )
    ).scalar_one()
    active_minutes_used = (
        await db.execute(select(func.coalesce(func.sum(Tenant.current_period_minutes_used), 0)).where(Tenant.status == "active"))
    ).scalar_one()

    return {
        "tenants_by_status": status_counts,
        "total_tenants": sum(status_counts.values()),
        "total_orders": total_orders,
        "total_topup_revenue_cents": total_revenue_cents,
        "total_charged_cents": total_charged_cents,
        "active_minutes_used_this_period": active_minutes_used,
    }


@router.get("/tenants")
async def list_tenants(status: str | None = None, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    query = select(Tenant)
    if status:
        query = query.where(Tenant.status == status)
    result = await db.execute(query.order_by(Tenant.created_at.desc()))
    return [_tenant_summary(t) for t in result.scalars().all()]


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    docs = (await db.execute(select(KycDocument).where(KycDocument.tenant_id == tenant_id))).scalars().all()
    phone = (await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant_id))).scalars().first()
    whatsapp = (await db.execute(select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id))).scalar_one_or_none()
    return {
        **_tenant_summary(tenant),
        "kyc_documents": [
            {"id": str(d.id), "doc_type": d.doc_type, "file_url": d.file_url, "review_status": d.review_status, "notes": d.notes}
            for d in docs
        ],
        "phone_number": phone.e164_number if phone else None,
        "whatsapp_connected": bool(whatsapp and whatsapp.verified_at),
    }


def _tenant_summary(t: Tenant) -> dict:
    return {
        "id": str(t.id), "business_name": t.business_name, "category": t.category,
        "status": t.status, "city": t.city, "created_at": t.created_at.isoformat(),
    }


class DocReviewBody(BaseModel):
    review_status: str  # approved, rejected
    notes: str | None = None


@router.post("/tenants/{tenant_id}/kyc-documents/{doc_id}/review")
async def review_document(tenant_id: uuid.UUID, doc_id: uuid.UUID, body: DocReviewBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    doc = await db.get(KycDocument, doc_id)
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    doc.review_status = body.review_status
    doc.notes = body.notes
    doc.reviewed_by = admin.email
    await db.commit()
    return {"ok": True}


class PhoneNumberBody(BaseModel):
    e164_number: str
    didww_reference: str | None = None


@router.post("/tenants/{tenant_id}/phone-number")
async def set_phone_number(tenant_id: uuid.UUID, body: PhoneNumberBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    db.add(PhoneNumber(tenant_id=tenant_id, e164_number=body.e164_number, didww_reference=body.didww_reference, status="active"))
    await db.commit()
    return {"ok": True}


class WhatsappChannelBody(BaseModel):
    phone_number_id: str
    waba_id: str | None = None
    access_token: str


@router.post("/tenants/{tenant_id}/whatsapp-channel")
async def set_whatsapp_channel(tenant_id: uuid.UUID, body: WhatsappChannelBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")

    existing = (await db.execute(select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id))).scalar_one_or_none()
    encrypted = encrypt_token(body.access_token)
    if existing:
        existing.phone_number_id = body.phone_number_id
        existing.waba_id = body.waba_id
        existing.access_token_encrypted = encrypted
    else:
        db.add(WhatsappChannel(
            tenant_id=tenant_id, phone_number_id=body.phone_number_id,
            waba_id=body.waba_id, access_token_encrypted=encrypted,
        ))
    await db.commit()
    return {"ok": True}


@router.post("/tenants/{tenant_id}/whatsapp-channel/verify")
async def verify_whatsapp_channel(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime
    channel = (await db.execute(select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id))).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Canale WhatsApp non configurato")
    channel.verified_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/tenants/{tenant_id}/reject")
async def reject_tenant(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    tenant.status = "rejected"
    await db.commit()
    return {"ok": True}


@router.post("/tenants/{tenant_id}/approve")
async def approve_tenant(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")

    plan = billing.plan_info(tenant.plan)
    if tenant.prepaid_balance_cents < plan["price_cents"]:
        raise HTTPException(
            status_code=400,
            detail=f"Credito insufficiente per attivare (servono almeno {plan['price_cents'] / 100:.2f} € per il canone {plan['name']}, saldo attuale {tenant.prepaid_balance_cents / 100:.2f} €). Ricarica prima da /dashboard/consumi.",
        )

    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))).scalar_one()
    prompt = await build_agent_prompt(db, tenant, channel="voice")
    first_message = f"Ciao, grazie per aver chiamato {tenant.business_name}! Come posso aiutarti?"

    try:
        if tenant.elevenlabs_agent_id:
            await update_agent(
                tenant.elevenlabs_agent_id, name=f"{tenant.business_name} - {settings_row.agent_persona_name}",
                prompt=prompt, first_message=first_message, voice_id=settings_row.agent_voice_id,
            )
        else:
            agent_id = await create_agent(
                name=f"{tenant.business_name} - {settings_row.agent_persona_name}",
                prompt=prompt, first_message=first_message, voice_id=settings_row.agent_voice_id,
            )
            tenant.elevenlabs_agent_id = agent_id
    except Exception as e:
        sys.stderr.write(f"Creazione agente ElevenLabs fallita per tenant {tenant_id}: {e}\n")
        raise HTTPException(status_code=502, detail="Creazione dell'agente ElevenLabs fallita, riprova")

    tenant.status = "active"
    tenant.billing_status = "active"
    await db.commit()
    await billing.charge_plan_renewal(db, tenant)

    owner = (await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "owner"))).scalars().first()
    if owner:
        try:
            await send_email(owner.email, f"{tenant.business_name} è ora attivo!", build_activation_email(tenant.business_name))
        except Exception as e:
            sys.stderr.write(f"Invio email di attivazione fallito per tenant {tenant_id}: {e}\n")

    return {"ok": True, "status": tenant.status, "elevenlabs_agent_id": tenant.elevenlabs_agent_id}


# --- Attivazione numero DIDWW: ricerca -> prenotazione -> identità/indirizzo
# -> documenti -> verifica -> ordine. Il numero finale va comunque confermato
# a mano con /phone-number una volta che DIDWW completa l'ordine (i tempi di
# elaborazione lato loro non sono garantiti in tempo reale via API).

async def _get_or_create_profile(db: AsyncSession, tenant_id: uuid.UUID) -> DidwwRegulatoryProfile:
    profile = (await db.execute(select(DidwwRegulatoryProfile).where(DidwwRegulatoryProfile.tenant_id == tenant_id))).scalar_one_or_none()
    if not profile:
        profile = DidwwRegulatoryProfile(tenant_id=tenant_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/tenants/{tenant_id}/didww/search")
async def didww_search(tenant_id: uuid.UUID, country_id: str, city_id: str | None = None, admin: AdminUser = Depends(get_current_admin)):
    try:
        results = await didww_client.search_available_dids(country_id, city_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ricerca DIDWW fallita: {e}")
    return results


class ReserveBody(BaseModel):
    available_did_id: str
    sku_id: str


@router.post("/tenants/{tenant_id}/didww/reserve")
async def didww_reserve(tenant_id: uuid.UUID, body: ReserveBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db, tenant_id)
    try:
        reservation = await didww_client.reserve_did(body.available_did_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Prenotazione DIDWW fallita: {e}")
    profile.available_did_id = body.available_did_id
    profile.did_reservation_id = reservation["id"]
    profile.sku_id = body.sku_id
    await db.commit()
    return {"ok": True, "expires_at": reservation.get("attributes", {}).get("expires_at")}


class IdentityBody(BaseModel):
    identity_type: str = "business"
    first_name: str
    last_name: str
    contact_email: str
    phone_number: str
    company_name: str | None = None
    company_reg_number: str | None = None


@router.post("/tenants/{tenant_id}/didww/identity")
async def didww_identity(tenant_id: uuid.UUID, body: IdentityBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db, tenant_id)
    try:
        identity_id = await didww_client.create_identity(**body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Creazione identità DIDWW fallita: {e}")
    profile.identity_id = identity_id
    await db.commit()
    return {"ok": True, "identity_id": identity_id}


class AddressBody(BaseModel):
    country_id: str
    city_name: str
    postal_code: str
    address: str


@router.post("/tenants/{tenant_id}/didww/address")
async def didww_address(tenant_id: uuid.UUID, body: AddressBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db, tenant_id)
    if not profile.identity_id:
        raise HTTPException(status_code=400, detail="Crea prima l'identità DIDWW")
    try:
        address_id = await didww_client.create_address(identity_id=profile.identity_id, **body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Creazione indirizzo DIDWW fallita: {e}")
    profile.address_id = address_id
    await db.commit()
    return {"ok": True, "address_id": address_id}


class UploadDocBody(BaseModel):
    kyc_document_id: uuid.UUID


@router.post("/tenants/{tenant_id}/didww/upload-document")
async def didww_upload_document(tenant_id: uuid.UUID, body: UploadDocBody, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    doc = await db.get(KycDocument, body.kyc_document_id)
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    filename = doc.file_url.rsplit("/", 1)[-1]
    disk_path = os.path.join(UPLOADS_DIR, str(tenant_id), filename)
    if not os.path.isfile(disk_path):
        raise HTTPException(status_code=404, detail="File non trovato su disco")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "application/octet-stream")

    with open(disk_path, "rb") as f:
        file_bytes = f.read()

    try:
        encrypted_file_id = await didww_client.upload_encrypted_file(file_bytes, filename, content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Caricamento documento su DIDWW fallito: {e}")

    profile = await _get_or_create_profile(db, tenant_id)
    profile.encrypted_file_ids = list(profile.encrypted_file_ids or []) + [encrypted_file_id]
    await db.commit()
    return {"ok": True, "encrypted_file_id": encrypted_file_id}


@router.post("/tenants/{tenant_id}/didww/verify")
async def didww_verify(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db, tenant_id)
    if not (profile.did_reservation_id and profile.address_id and profile.encrypted_file_ids):
        raise HTTPException(status_code=400, detail="Servono prenotazione, indirizzo e almeno un documento caricato prima di avviare la verifica")

    try:
        verification = await didww_client.create_address_verification(
            did_reservation_id=profile.did_reservation_id,
            address_id=profile.address_id,
            encrypted_file_ids=profile.encrypted_file_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Avvio verifica DIDWW fallito: {e}")

    profile.verification_id = verification["id"]
    profile.verification_status = verification.get("attributes", {}).get("status")
    await db.commit()
    return {"ok": True, "status": profile.verification_status}


@router.get("/tenants/{tenant_id}/didww/status")
async def didww_status(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(DidwwRegulatoryProfile).where(DidwwRegulatoryProfile.tenant_id == tenant_id))).scalar_one_or_none()
    if not profile:
        return {"exists": False}

    if profile.verification_id and profile.verification_status not in ("approved", "rejected"):
        try:
            verification = await didww_client.get_verification_status(profile.verification_id)
            profile.verification_status = verification.get("attributes", {}).get("status")
            await db.commit()
        except Exception as e:
            sys.stderr.write(f"Aggiornamento stato verifica DIDWW fallito per tenant {tenant_id}: {e}\n")

    return {
        "exists": True,
        "did_reservation_id": profile.did_reservation_id,
        "identity_id": profile.identity_id,
        "address_id": profile.address_id,
        "documents_uploaded": len(profile.encrypted_file_ids or []),
        "verification_status": profile.verification_status,
        "order_id": profile.order_id,
        "order_status": profile.order_status,
    }


@router.post("/tenants/{tenant_id}/didww/order")
async def didww_order(tenant_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db, tenant_id)
    if profile.verification_status != "approved":
        raise HTTPException(status_code=400, detail="La verifica DIDWW deve risultare 'approved' prima di ordinare il numero")
    if not (profile.did_reservation_id and profile.sku_id):
        raise HTTPException(status_code=400, detail="Manca la prenotazione del numero")

    try:
        order = await didww_client.create_order(did_reservation_id=profile.did_reservation_id, sku_id=profile.sku_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ordine DIDWW fallito: {e}")

    profile.order_id = order["id"]
    profile.order_status = order.get("attributes", {}).get("status")
    await db.commit()
    return {
        "ok": True, "order_id": profile.order_id, "order_status": profile.order_status,
        "note": "Quando DIDWW conferma il numero, inseriscilo in /phone-number per completare l'attivazione.",
    }
