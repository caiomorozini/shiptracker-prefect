"""
Script de debug para testar o payload enviado à API
"""
from dotenv import load_dotenv
import httpx
import json
import os
from datetime import datetime

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("CRONJOB_API_KEY", "")

if not API_KEY:
    print("❌ CRONJOB_API_KEY não configurada!")
    exit(1)

# Exemplo de payload que será enviado (dados realistas do SSW)
test_payload = {
    "tracking_code": None,
    "invoice_number": "123456",
    "document": "12345678000199",
    "carrier": "SSW",
    "current_status": "EM TRANSITO PARA A UNIDADE DESTINO",
    "events": [
        {
            "occurrence_code": None,  # Código será extraído do texto
            "status": "EM TRANSITO PARA A UNIDADE DESTINO",
            "description": "EM TRANSITO PARA A UNIDADE DESTINO  (SSW WebAPI Parceiro).",
            "location": "SAO PAULO",
            "unit": "0048",
            "occurred_at": "2025-11-19T08:36:00"
        },
        {
            "occurrence_code": "01",
            "status": "Nota Fiscal Eletrônica emitida",
            "description": "Nota Fiscal Eletrônica emitida  01",
            "location": "São Paulo SP",
            "unit": "0001",
            "occurred_at": datetime.now().isoformat()
        }
    ],
    "last_update": datetime.now().isoformat()
}

print("="*60)
print("🧪 Teste de Payload para API")
print("="*60)

print("\n📦 Payload que será enviado:")
print(json.dumps(test_payload, indent=2, ensure_ascii=False))

print(f"\n🔗 URL: {API_BASE_URL}/tracking-updates/shipment")
print(f"🔑 API Key: {API_KEY[:10]}...{API_KEY[-5:]}")

print("\n📤 Enviando requisição...")

try:
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{API_BASE_URL}/tracking-updates/shipment",
            json=test_payload,
            headers={"X-API-Key": API_KEY}
        )
        
        print(f"\n📥 Status Code: {response.status_code}")
        print(f"📥 Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("\n✅ Sucesso!")
            result = response.json()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n❌ Erro!")
            print(f"Response: {response.text}")
            
            # Tentar parsear o erro
            try:
                error_detail = response.json()
                print("\nDetalhes do erro:")
                print(json.dumps(error_detail, indent=2, ensure_ascii=False))
            except:
                pass

except Exception as e:
    print(f"\n❌ Exceção: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
