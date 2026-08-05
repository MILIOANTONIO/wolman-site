"""
Verifica se un numero DIDWW prenotato e' davvero attivo, per tenere un
"database dei numeri attivi" reale invece di aspettare che qualcuno lo
controlli a mano: la verifica KYC dell'indirizzo (documenti che devono
corrispondere all'intestatario, personale o camera di commercio per le
aziende) viene revisionata da DIDWW entro circa 48 ore - finche' non e'
approvata il numero esiste ma non instrada ancora le chiamate.
"""
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DidwwRegulatoryProfile, PhoneNumber, Tenant
from app.services import didww_client
from app.services.elevenlabs_agents import import_phone_number


async def refresh_did_activation(db: AsyncSession, profile: DidwwRegulatoryProfile) -> None:
    if profile.verification_id and profile.verification_status not in ("approved", "rejected"):
        try:
            verification = await didww_client.get_verification_status(profile.verification_id)
            profile.verification_status = verification.get("attributes", {}).get("status")
            reasons = verification.get("attributes", {}).get("reject_reasons")
            profile.verification_reject_reason = "; ".join(reasons) if reasons else None
        except Exception as e:
            sys.stderr.write(f"Aggiornamento verifica DIDWW fallito per profilo {profile.id}: {e}\n")

    if not profile.order_id:
        profile.activation_status = "non_ordinato"
    elif not profile.phone_number:
        # Non dovrebbe succedere (il numero si conosce gia' alla prenotazione),
        # ma senza il numero non possiamo cercare la risorsa "dids" reale.
        profile.activation_status = "in_elaborazione"
    else:
        did = None
        try:
            did = await didww_client.find_did_by_number(profile.phone_number)
        except Exception as e:
            sys.stderr.write(f"Lookup DID {profile.phone_number} fallito per profilo {profile.id}: {e}\n")

        if not did:
            profile.activation_status = "in_elaborazione"
        else:
            profile.did_id = did["id"]
            attrs = did.get("attributes", {})
            # "blocked" e' vero anche durante la revisione KYC iniziale (non
            # e' un problema, e' lo stato normale finche' non e' registrato)
            # - va trattato come blocco vero solo se capita DOPO che la
            # registrazione e' gia' completata (es. sospensione per mancato
            # pagamento).
            if attrs.get("terminated"):
                profile.activation_status = "scaduto"
            elif attrs.get("awaiting_registration"):
                profile.activation_status = "in_verifica"
            elif attrs.get("blocked"):
                profile.activation_status = "bloccato"
            else:
                profile.activation_status = "attivo"

    if profile.activation_status == "attivo":
        existing = (
            await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == profile.tenant_id))
        ).scalars().first()
        if not existing:
            tenant = await db.get(Tenant, profile.tenant_id)
            e164_number = f"+{profile.phone_number}"
            elevenlabs_phone_number_id = None
            try:
                # Se l'agente non esiste ancora (numero attivato prima
                # dell'approvazione admin), importiamo comunque il numero ma
                # senza agente assegnato - viene collegato in un secondo
                # momento quando l'agente viene creato (vedi admin.py).
                elevenlabs_phone_number_id = await import_phone_number(
                    e164_number=e164_number, label=tenant.business_name if tenant else e164_number,
                    agent_id=tenant.elevenlabs_agent_id if tenant else None,
                )
            except Exception as e:
                sys.stderr.write(f"Import numero {e164_number} su ElevenLabs fallito per tenant {profile.tenant_id}: {e}\n")
            db.add(PhoneNumber(
                tenant_id=profile.tenant_id, e164_number=e164_number, didww_reference=profile.did_id,
                elevenlabs_phone_number_id=elevenlabs_phone_number_id, status="active",
            ))

    await db.commit()
