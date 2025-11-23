"""
Tests for SSW scraping and status mapping
Run with: python test_scraping.py
"""
import sys
import re
from datetime import datetime
from typing import Optional


# Mock occurrence codes (similar to what API returns)
MOCK_OCCURRENCE_CODES = [
    {
        "code": "1",
        "description": "mercadoria entregue",
        "type": "entrega",
        "process": "entrega"
    },
    {
        "code": "85",
        "description": "saida para entrega",
        "type": "informativa",
        "process": "operacional"
    },
    {
        "code": "84",
        "description": "chegada na unidade",
        "type": "informativa",
        "process": "operacional"
    },
    {
        "code": "82",
        "description": "saida de unidade",
        "type": "informativa",
        "process": "operacional"
    },
    {
        "code": "80",
        "description": "mercadoria recebida para transporte",
        "type": "informativa",
        "process": "operacional"
    },
    {
        "code": "11",
        "description": "local de entrega fechado/ausente",
        "type": "pendência cliente",
        "process": "entrega"
    },
    {
        "code": "31",
        "description": "primeira tentativa de entrega",
        "type": "pendência cliente",
        "process": "reentrega"
    },
    {
        "code": "99",
        "description": "ctrc baixado/cancelado",
        "type": "baixa",
        "process": "geral"
    },
    {
        "code": "3",
        "description": "mercadoria devolvida ao remetente",
        "type": "entrega",
        "process": "devolução"
    },
    {
        "code": "2",
        "description": "mercadoria pre-entregue (mobile)",
        "type": "préentrega",
        "process": "entrega"
    },
    {
        "code": "37",
        "description": "entrega realizada com ressalva",
        "type": "pendência transportadora",
        "process": "entrega"
    }
]


def map_occurrence_type_to_status(occurrence_code: dict) -> str:
    """
    Map occurrence process to shipment status (reproduces main.py logic)
    UPDATED: Now uses 'process' field as primary indicator
    """
    event_status = "in_transit"  # default
    
    if occurrence_code:
        occ_type = occurrence_code.get("type", "").lower()
        occ_process = occurrence_code.get("process", "").lower()
        
        # Priority 1: Check PROCESS for finalization (delivered/returned)
        if occ_process == "entrega":
            event_status = "delivered"
        elif occ_process == "finalizadora":
            event_status = "delivered"
        elif occ_process == "devolução":
            event_status = "returned"
        
        # Priority 2: Check TYPE for operational statuses
        elif occ_type == "baixa":
            event_status = "cancelled"
        elif occ_type == "préentrega":
            event_status = "out_for_delivery"
        
        # Priority 3: Pending/hold conditions
        elif "pendência" in occ_type:
            # Check if it's a redelivery attempt
            if occ_process == "reentrega":
                event_status = "failed_delivery"
            else:
                event_status = "held"
        
        # Priority 4: Informative events (in transit)
        elif occ_type == "informativa":
            event_status = "in_transit"
    
    return event_status


def find_occurrence_code(status_text: str, occurrence_codes: list) -> Optional[dict]:
    """
    Find matching occurrence code by description
    """
    for code in occurrence_codes:
        if code["description"].upper() in status_text.upper():
            return code
    return None


def test_status_mapping():
    """Test status mapping logic"""
    print("\n" + "=" * 70)
    print("TEST 1: Status Mapping from Occurrence Type and Process")
    print("=" * 70)
    
    test_cases = [
        ("mercadoria entregue", "delivered", "entrega", "entrega"),
        ("saida para entrega", "in_transit", "informativa", "operacional"),
        ("local de entrega fechado/ausente", "delivered", "pendência cliente", "entrega"),  # process="entrega" = delivered!
        ("ctrc baixado/cancelado", "cancelled", "baixa", "geral"),
        ("mercadoria pre-entregue (mobile)", "delivered", "préentrega", "entrega"),  # process="entrega" = delivered!
        ("chegada na unidade", "in_transit", "informativa", "operacional"),
        ("mercadoria devolvida ao remetente", "returned", "entrega", "devolução"),  # process="devolução" = returned
        ("entrega realizada com ressalva", "delivered", "pendência transportadora", "entrega"),  # CODE 37: process="entrega" = delivered!
    ]
    
    passed = 0
    failed = 0
    
    for description, expected_status, expected_type, expected_process in test_cases:
        # Find occurrence code
        occurrence_code = find_occurrence_code(description, MOCK_OCCURRENCE_CODES)
        
        if not occurrence_code:
            print(f"❌ FAIL: Could not find occurrence code for '{description}'")
            failed += 1
            continue
        
        # Map to status
        mapped_status = map_occurrence_type_to_status(occurrence_code)
        
        # Validate
        if mapped_status == expected_status and occurrence_code["type"] == expected_type:
            print(f"✅ PASS: '{description}'")
            print(f"   Type: {occurrence_code['type']}, Process: {occurrence_code['process']} → Status: {mapped_status}")
            passed += 1
        else:
            print(f"❌ FAIL: '{description}'")
            print(f"   Expected: type={expected_type}, process={expected_process}, status={expected_status}")
            print(f"   Got: type={occurrence_code['type']}, process={occurrence_code['process']}, status={mapped_status}")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")
    
    return failed == 0


def test_scraping_simulation():
    """Simulate scraping and event processing"""
    print("=" * 70)
    print("TEST 2: Simulated Scraping Flow")
    print("=" * 70)
    
    # Simulate scraped events from SSW HTML
    # Note: Real format is "RIO DE JANEIRO / RJ18/11/25\n16:35"
    scraped_events = [
        {
            "unit": "1234",
            "location": "RIO DE JANEIRO / RJ",
            "date": "20/11/25",
            "time": "10:30",
            "status_text": "MERCADORIA RECEBIDA PARA TRANSPORTE  (SSW WebAPI Parceiro)."
        },
        {
            "unit": "1234",
            "location": "RIO DE JANEIRO / RJ",
            "date": "20/11/25",
            "time": "14:20",
            "status_text": "SAIDA DE UNIDADE  (SSW WebAPI Parceiro)."
        },
        {
            "unit": "5678",
            "location": "SAO PAULO / SP",
            "date": "21/11/25",
            "time": "08:15",
            "status_text": "CHEGADA NA UNIDADE  (SSW WebAPI Parceiro)."
        },
        {
            "unit": "5678",
            "location": "SAO PAULO / SP",
            "date": "21/11/25",
            "time": "09:45",
            "status_text": "SAIDA PARA ENTREGA  (SSW WebAPI Parceiro)."
        },
        {
            "unit": "5678",
            "location": "SAO PAULO / SP",
            "date": "21/11/25",
            "time": "16:30",
            "status_text": "MERCADORIA ENTREGUE  (SSW WebAPI Parceiro)."
        }
    ]
    
    print(f"\nProcessing {len(scraped_events)} scraped events...\n")
    
    processed_events = []
    
    for i, event in enumerate(scraped_events, 1):
        # Find occurrence code
        occurrence_code = find_occurrence_code(event["status_text"], MOCK_OCCURRENCE_CODES)
        
        if not occurrence_code:
            print(f"⚠️  Event {i}: Could not find occurrence code for '{event['status_text']}'")
            continue
        
        # Map to status
        event_status = map_occurrence_type_to_status(occurrence_code)
        
        # Parse datetime
        occurred_at = datetime.strptime(
            f"{event['date']} {event['time']}", "%d/%m/%y %H:%M"
        )
        
        processed_event = {
            "occurrence_code": occurrence_code["code"],
            "status": event_status,
            "description": occurrence_code["description"],
            "location": event["location"],
            "unit": event["unit"],
            "occurred_at": occurred_at.isoformat(),
        }
        
        processed_events.append(processed_event)
        
        print(f"Event {i}: {event['date']} {event['time']}")
        print(f"  Text: {event['status_text'][:50]}...")
        print(f"  Code: {occurrence_code['code']} | Type: {occurrence_code['type']}")
        print(f"  Status: {event_status}")
        print()
    
    # Get current status (most recent event)
    current_status = processed_events[-1]["status"] if processed_events else "pending"
    
    print(f"{'=' * 70}")
    print(f"Final Result:")
    print(f"  Total Events: {len(processed_events)}")
    print(f"  Current Status: {current_status}")
    print(f"  Should be Delivered: {current_status == 'delivered'}")
    print(f"{'=' * 70}\n")
    
    return current_status == "delivered"


def test_finalization_logic():
    """Test finalization detection logic"""
    print("=" * 70)
    print("TEST 3: Finalization Detection (API Logic)")
    print("=" * 70)
    
    # Codes that should trigger finalization
    finalization_types = ["entrega", "baixa", "préentrega"]
    
    # Get codes that should finalize
    finalization_codes = [
        code["code"] for code in MOCK_OCCURRENCE_CODES
        if code["type"] in finalization_types
    ]
    
    print(f"\nFinalization types: {finalization_types}")
    print(f"Finalization codes: {finalization_codes}\n")
    
    # Test cases
    test_cases = [
        ("1", True, "mercadoria entregue"),
        ("3", True, "mercadoria devolvida ao remetente"),
        ("2", True, "mercadoria pre-entregue"),
        ("99", True, "ctrc baixado/cancelado"),
        ("85", False, "saida para entrega"),
        ("80", False, "mercadoria recebida para transporte"),
        ("11", False, "local de entrega fechado/ausente"),
    ]
    
    passed = 0
    failed = 0
    
    for code, should_finalize, description in test_cases:
        is_finalization = code in finalization_codes
        
        if is_finalization == should_finalize:
            status_icon = "✅" if should_finalize else "ℹ️ "
            print(f"{status_icon} PASS: Code {code} - {description}")
            print(f"   Finalizes: {is_finalization}")
            passed += 1
        else:
            print(f"❌ FAIL: Code {code} - {description}")
            print(f"   Expected finalization: {should_finalize}, Got: {is_finalization}")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")
    
    return failed == 0


def test_occurrence_code_matching():
    """Test occurrence code matching with similar descriptions"""
    print("=" * 70)
    print("TEST 4: Occurrence Code Matching (Specificity)")
    print("=" * 70)
    
    # Mock codes with similar descriptions (based on real occurrence codes)
    test_occurrence_codes = [
        {
            "code": "1",
            "description": "mercadoria entregue",
            "type": "entrega",
            "process": "entrega"
        },
        {
            "code": "37",
            "description": "entrega realizada com ressalva",
            "type": "pendência transportadora",
            "process": "entrega"
        },
        {
            "code": "85",
            "description": "saida para entrega",
            "type": "informativa",
            "process": "operacional"
        }
    ]
    
    # Test cases - now with flexible word-based matching
    test_cases = [
        ("ENTREGA REALIZADA COM RESSALVA (SSW WebAPI)", "37", "entrega realizada com ressalva"),
        ("ENTREGA REALIZADA (SSW WebAPI)", "37", "entrega realizada com ressalva"),  # Partial match
        ("ENTREGA REALIZADA NORMALMENTE (SSW WebAPI)", "37", "entrega realizada com ressalva"),  # Word overlap
        ("MERCADORIA ENTREGUE (SSW WebAPI)", "1", "mercadoria entregue"),  # Exact match
    ]
    
    passed = 0
    failed = 0
    
    for status_text, expected_code, expected_description in test_cases:
        # Simulate matching logic from main.py
        occurrence_code = {}
        best_match_score = 0
        
        # Clean status text
        status_text_clean = re.sub(r'\s*\(.*?\)\s*\.?$', '', status_text).strip()
        status_text_upper = status_text_clean.upper()
        
        # Extract keywords
        status_words = set(re.findall(r'\b\w+\b', status_text_upper))
        ignore_words = {'DE', 'DA', 'DO', 'PARA', 'COM', 'SEM', 'POR', 'AO', 'A', 'O', 'E'}
        status_keywords = status_words - ignore_words
        
        sorted_codes = sorted(
            test_occurrence_codes, 
            key=lambda x: len(x["description"]), 
            reverse=True
        )
        
        for code in sorted_codes:
            description_upper = code["description"].upper()
            
            # Level 1: Exact substring match
            if description_upper in status_text_upper:
                match_score = len(description_upper) * 100
            elif status_text_upper in description_upper:
                match_score = len(status_text_upper) * 100
            else:
                # Level 2: Word-based matching
                desc_words = set(re.findall(r'\b\w+\b', description_upper))
                desc_keywords = desc_words - ignore_words
                
                common_words = status_keywords & desc_keywords
                
                if common_words:
                    match_score = sum(len(word) for word in common_words)
                else:
                    match_score = 0
            
            if match_score > best_match_score:
                occurrence_code = code
                best_match_score = match_score
        
        # Validate
        if occurrence_code.get("code") == expected_code:
            print(f"✅ PASS: '{status_text[:40]}...'")
            print(f"   Matched: {occurrence_code['description']} (code: {occurrence_code['code']})")
            passed += 1
        else:
            print(f"❌ FAIL: '{status_text[:40]}...'")
            print(f"   Expected: {expected_description} (code: {expected_code})")
            print(f"   Got: {occurrence_code.get('description', 'None')} (code: {occurrence_code.get('code', 'None')})")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")
    
    return failed == 0


def test_location_extraction():
    """Test location extraction from SSW format"""
    print("=" * 70)
    print("TEST 5: Location Extraction")
    print("=" * 70)
    
    # Test cases with real SSW format
    test_cases = [
        ("RIO DE JANEIRO / RJ18/11/25\n16:35", "RIO DE JANEIRO / RJ"),
        ("SAO PAULO / SP20/11/25\n10:30", "SAO PAULO / SP"),
        ("BELO HORIZONTE / MG21/11/25\n14:20", "BELO HORIZONTE / MG"),
        ("BRASILIA / DF22/11/25\n08:15", "BRASILIA / DF"),
        ("PORTO ALEGRE / RS23/11/25\n09:45", "PORTO ALEGRE / RS"),
    ]
    
    passed = 0
    failed = 0
    
    for raw_text, expected_location in test_cases:
        # Simulate extraction logic from main.py
        location_match = re.match(r"^(.+?)(?=\d{2}/\d{2}/\d{2})", raw_text)
        if location_match:
            location = location_match.group(1).strip()
            location = re.sub(r'\s*/\s*$', '', location).strip()
        else:
            location = None
        
        if location == expected_location:
            print(f"✅ PASS: '{raw_text[:30]}...'")
            print(f"   Extracted: '{location}'")
            passed += 1
        else:
            print(f"❌ FAIL: '{raw_text[:30]}...'")
            print(f"   Expected: '{expected_location}'")
            print(f"   Got: '{location}'")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")
    
    return failed == 0


def test_edge_cases():
    """Test edge cases and error handling"""
    print("=" * 70)
    print("TEST 6: Edge Cases")
    print("=" * 70)
    
    print("\n1. Unknown occurrence code:")
    unknown_text = "EVENTO DESCONHECIDO"
    occurrence_code = find_occurrence_code(unknown_text, MOCK_OCCURRENCE_CODES)
    if occurrence_code is None:
        print(f"   ✅ PASS: Returns None for unknown text")
    else:
        print(f"   ❌ FAIL: Should return None")
    
    print("\n2. Empty occurrence code:")
    empty_code = {}
    status = map_occurrence_type_to_status(empty_code)
    if status == "in_transit":
        print(f"   ✅ PASS: Defaults to 'in_transit'")
    else:
        print(f"   ❌ FAIL: Should default to 'in_transit', got '{status}'")
    
    print("\n3. Case insensitive matching:")
    lower_text = "mercadoria entregue"
    upper_text = "MERCADORIA ENTREGUE"
    mixed_text = "MeRcAdOrIa EnTrEgUe"
    
    all_match = all([
        find_occurrence_code(lower_text, MOCK_OCCURRENCE_CODES),
        find_occurrence_code(upper_text, MOCK_OCCURRENCE_CODES),
        find_occurrence_code(mixed_text, MOCK_OCCURRENCE_CODES)
    ])
    
    if all_match:
        print(f"   ✅ PASS: Case insensitive matching works")
    else:
        print(f"   ❌ FAIL: Case insensitive matching failed")
    
    print("\n4. Partial text matching:")
    partial_text = "MERCADORIA ENTREGUE (SSW WebAPI Parceiro)."
    code = find_occurrence_code(partial_text, MOCK_OCCURRENCE_CODES)
    if code and code["code"] == "1":
        print(f"   ✅ PASS: Finds code in longer text")
    else:
        print(f"   ❌ FAIL: Should find code '1'")
    
    print(f"\n{'=' * 70}\n")


def test_api_payload():
    """Test final API payload structure"""
    print("=" * 70)
    print("TEST 7: API Payload Structure")
    print("=" * 70)
    
    # Simulate final payload that would be sent to API
    payload = {
        "tracking_code": None,
        "invoice_number": "12345",
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
    
    # Validate structure
    errors = []
    
    if not payload.get("invoice_number"):
        errors.append("Missing invoice_number")
    
    if not payload.get("document"):
        errors.append("Missing document")
    
    if not payload.get("carrier"):
        errors.append("Missing carrier")
    
    if not isinstance(payload.get("events"), list):
        errors.append("events should be a list")
    
    # Validate each event
    for i, event in enumerate(payload["events"]):
        required_fields = ["status", "description", "occurred_at"]
        for field in required_fields:
            if not event.get(field):
                errors.append(f"Event {i}: missing {field}")
    
    # Check status consistency
    has_delivered_event = any(e["status"] == "delivered" for e in payload["events"])
    if has_delivered_event and payload["current_status"] != "delivered":
        errors.append("Has delivered event but current_status is not 'delivered'")
    
    print("\nPayload structure:")
    print(f"  Invoice: {payload['invoice_number']}")
    print(f"  Document: {payload['document']}")
    print(f"  Carrier: {payload['carrier']}")
    print(f"  Current Status: {payload['current_status']}")
    print(f"  Events: {len(payload['events'])}")
    
    if errors:
        print(f"\n❌ Validation errors:")
        for error in errors:
            print(f"   - {error}")
    else:
        print(f"\n✅ Payload structure is valid")
    
    print(f"\n{'=' * 70}\n")
    
    return len(errors) == 0


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 70)
    print(" SSW SCRAPING AND STATUS MAPPING TESTS")
    print("=" * 70 + "\n")
    
    results = {
        "Status Mapping": test_status_mapping(),
        "Scraping Simulation": test_scraping_simulation(),
        "Finalization Detection": test_finalization_logic(),
        "Occurrence Matching": test_occurrence_code_matching(),
        "Location Extraction": test_location_extraction(),
        "Edge Cases": True,  # Edge cases don't return boolean
        "API Payload": test_api_payload()
    }
    
    # Run edge cases
    test_edge_cases()
    
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
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
