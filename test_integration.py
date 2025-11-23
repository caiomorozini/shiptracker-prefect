"""
Integration test script to validate the full flow
Run with: python test_integration.py

This script tests:
1. API is running and accessible
2. Occurrence codes are seeded
3. Can create shipment via tracking-updates endpoint
4. Finalization logic works correctly
"""
import os
import sys
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("CRONJOB_API_KEY", "")

if not API_KEY:
    print("❌ Error: CRONJOB_API_KEY not set in environment")
    sys.exit(1)

HEADERS = {"X-API-Key": API_KEY}


def test_api_health():
    """Test if API is accessible"""
    print("\n" + "=" * 70)
    print("TEST 1: API Health Check")
    print("=" * 70)
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{API_BASE_URL.replace('/api/v1', '')}/health")
            
            if response.status_code == 200:
                print("✅ PASS: API is running")
                return True
            else:
                print(f"⚠️  WARNING: API returned {response.status_code}")
                return True  # Still continue
    except Exception as e:
        print(f"❌ FAIL: Cannot connect to API at {API_BASE_URL}")
        print(f"   Error: {e}")
        return False


def test_occurrence_codes_endpoint():
    """Test occurrence codes endpoint"""
    print("\n" + "=" * 70)
    print("TEST 2: Occurrence Codes Endpoint")
    print("=" * 70)
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{API_BASE_URL}/tracking-updates/occurrence-codes",
                headers=HEADERS
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: API returned {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
            
            codes = response.json()
            
            if not isinstance(codes, list):
                print("❌ FAIL: Response is not a list")
                return False
            
            if len(codes) == 0:
                print("⚠️  WARNING: No occurrence codes found")
                print("   Run: python scripts/seed_occurrence_codes.py")
                return False
            
            # Validate structure
            required_fields = ["code", "description", "type", "process"]
            for code in codes[:3]:  # Check first 3
                for field in required_fields:
                    if field not in code:
                        print(f"❌ FAIL: Missing field '{field}' in occurrence code")
                        return False
            
            # Check for finalization codes
            finalization_types = ["entrega", "baixa", "préentrega"]
            finalization_codes = [
                c["code"] for c in codes 
                if c["type"] in finalization_types
            ]
            
            print(f"✅ PASS: Found {len(codes)} occurrence codes")
            print(f"   Finalization codes: {len(finalization_codes)} ({', '.join(finalization_codes[:5])}...)")
            
            return True
            
    except Exception as e:
        print(f"❌ FAIL: Error fetching occurrence codes")
        print(f"   Error: {e}")
        return False


def test_create_shipment_in_transit():
    """Test creating shipment with in_transit status"""
    print("\n" + "=" * 70)
    print("TEST 3: Create Shipment (In Transit)")
    print("=" * 70)
    
    invoice_number = f"TEST-TRANSIT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    payload = {
        "tracking_code": None,
        "invoice_number": invoice_number,
        "document": "12345678000199",
        "carrier": "SSW",
        "current_status": "in_transit",
        "events": [
            {
                "occurrence_code": "80",
                "status": "in_transit",
                "description": "mercadoria recebida para transporte",
                "location": "RIO DE JANEIRO RJ",
                "unit": "1234",
                "occurred_at": "2025-11-20T10:30:00"
            }
        ],
        "last_update": datetime.now().isoformat()
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{API_BASE_URL}/tracking-updates/shipment",
                json=payload,
                headers=HEADERS
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: API returned {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
            
            data = response.json()
            
            if not data.get("success"):
                print("❌ FAIL: Response success=False")
                print(f"   Errors: {data.get('errors', [])}")
                return False
            
            print(f"✅ PASS: Created shipment")
            print(f"   Shipment ID: {data['shipment_id']}")
            print(f"   Events created: {data['events_created']}")
            print(f"   Invoice: {invoice_number}")
            
            return True
            
    except Exception as e:
        print(f"❌ FAIL: Error creating shipment")
        print(f"   Error: {e}")
        return False


def test_create_shipment_delivered():
    """Test creating shipment with delivered status (finalization)"""
    print("\n" + "=" * 70)
    print("TEST 4: Create Shipment (Delivered - Finalization)")
    print("=" * 70)
    
    invoice_number = f"TEST-DELIVERED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    payload = {
        "tracking_code": None,
        "invoice_number": invoice_number,
        "document": "12345678000199",
        "carrier": "SSW",
        "current_status": "delivered",
        "events": [
            {
                "occurrence_code": "80",
                "status": "in_transit",
                "description": "mercadoria recebida para transporte",
                "location": "RIO DE JANEIRO RJ",
                "unit": "1234",
                "occurred_at": "2025-11-20T10:30:00"
            },
            {
                "occurrence_code": "1",
                "status": "delivered",
                "description": "mercadoria entregue",
                "location": "SAO PAULO SP",
                "unit": "5678",
                "occurred_at": "2025-11-21T16:30:00"
            }
        ],
        "last_update": datetime.now().isoformat()
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{API_BASE_URL}/tracking-updates/shipment",
                json=payload,
                headers=HEADERS
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: API returned {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
            
            data = response.json()
            
            if not data.get("success"):
                print("❌ FAIL: Response success=False")
                print(f"   Errors: {data.get('errors', [])}")
                return False
            
            print(f"✅ PASS: Created shipment with delivered event")
            print(f"   Shipment ID: {data['shipment_id']}")
            print(f"   Events created: {data['events_created']}")
            print(f"   Invoice: {invoice_number}")
            print(f"   ⚠️  Note: Check database to confirm status='delivered'")
            
            return True
            
    except Exception as e:
        print(f"❌ FAIL: Error creating shipment")
        print(f"   Error: {e}")
        return False


def test_get_pending_shipments():
    """Test getting pending shipments"""
    print("\n" + "=" * 70)
    print("TEST 5: Get Pending Shipments")
    print("=" * 70)
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{API_BASE_URL}/tracking-updates/pending-shipments",
                headers=HEADERS,
                params={"limit": 10}
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: API returned {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
            
            shipments = response.json()
            
            if not isinstance(shipments, list):
                print("❌ FAIL: Response is not a list")
                return False
            
            print(f"✅ PASS: Retrieved pending shipments")
            print(f"   Total pending: {len(shipments)}")
            
            if len(shipments) > 0:
                print(f"\n   Sample shipments:")
                for shipment in shipments[:3]:
                    print(f"   - {shipment['invoice_number']} | Status: {shipment['status']}")
            
            return True
            
    except Exception as e:
        print(f"❌ FAIL: Error fetching pending shipments")
        print(f"   Error: {e}")
        return False


def run_integration_tests():
    """Run all integration tests"""
    print("\n" + "=" * 70)
    print(" INTEGRATION TESTS - ShipTracker Tracking Updates")
    print("=" * 70)
    print(f"\n API: {API_BASE_URL}")
    print(f" API Key: {'*' * 10}{API_KEY[-4:] if len(API_KEY) > 4 else '****'}")
    
    results = {}
    
    # Run tests in sequence
    results["API Health"] = test_api_health()
    
    if not results["API Health"]:
        print("\n❌ Cannot continue - API is not accessible")
        return False
    
    results["Occurrence Codes"] = test_occurrence_codes_endpoint()
    results["Create In Transit"] = test_create_shipment_in_transit()
    results["Create Delivered"] = test_create_shipment_delivered()
    results["Get Pending"] = test_get_pending_shipments()
    
    # Summary
    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("=" * 70)
    if all_passed:
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("\nNext steps:")
        print("1. Check database to verify shipments were created")
        print("2. Run the Prefect scraper: python main.py")
        print("3. Monitor logs for any issues")
        return True
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
        print("\nTroubleshooting:")
        print("1. Ensure API is running: cd shiptracker-api && uvicorn app.main:app")
        print("2. Seed occurrence codes: python scripts/seed_occurrence_codes.py")
        print("3. Check .env file has correct CRONJOB_API_KEY")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
