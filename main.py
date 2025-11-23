from dotenv import load_dotenv
from prefect import flow, task
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import Optional
import os

load_dotenv()

# API Configuration
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
API_KEY: str = os.getenv("CRONJOB_API_KEY", "")

if not API_KEY:
    raise ValueError("CRONJOB_API_KEY environment variable is required")


@task
def scrape_ssw_tracking(cnpj: str, invoice_number: str, occurrence_codes: list[dict]) -> Optional[dict]:
    """
    Scrape tracking data from SSW website
    Returns parsed tracking data or None if failed
    
    Args:
        cnpj: Customer CNPJ
        invoice_number: Invoice number to track
        occurrence_codes: Pre-fetched list of occurrence codes from API
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://ssw.inf.br/2/resultSSW_dest_nro",
                data={"cnpjdest": cnpj, "NR": invoice_number},
            )
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html5lib")

        # Extract all tracking events from paragraphs with class "tdb"
        # The HTML structure has 3 consecutive <p class="tdb"> for each event:
        # 1. Unit code
        # 2. Location and datetime
        # 3. Status and occurrence code
        tracking_paragraphs = soup.find_all("p", class_="tdb")

        events = []

        # Process paragraphs in groups of 3
        for i in range(0, len(tracking_paragraphs), 3):
            if i + 2 < len(tracking_paragraphs):
                unit_text = tracking_paragraphs[i].get_text(strip=True)
                location_datetime = tracking_paragraphs[i + 1].get_text(strip=True)
                status_text = tracking_paragraphs[i + 2].get_text(strip=True)

                # Extract unit (código da unidade)
                unit_match = re.search(r"(\d{4})", unit_text)
                unit = unit_match.group(1) if unit_match else None

                # Extract location (format: "RIO DE JANEIRO / RJ18/11/25\n16:35")
                # Split by date pattern to separate location from datetime
                location_match = re.match(r"^(.+?)(?=\d{2}/\d{2}/\d{2})", location_datetime)
                if location_match:
                    location = location_match.group(1).strip()
                    # Clean up any trailing slashes or spaces
                    location = re.sub(r'\s*/\s*$', '', location).strip()
                else:
                    location = None

                # Extract date and time
                date_match = re.search(r"(\d{2}/\d{2}/\d{2})", location_datetime)
                time_match = re.search(r"(\d{2}:\d{2})", location_datetime)

                if date_match and time_match:
                    # Parse datetime (format: DD/MM/YY HH:MM)
                    date_str = date_match.group(1)
                    time_str = time_match.group(1)
                    occurred_at = datetime.strptime(
                        f"{date_str} {time_str}", "%d/%m/%y %H:%M"
                    )

                    # Extract status and occurrence code from status_text
                    # Example: "MERCADORIA ENTREGUE  (SSW WebAPI Parceiro)."
                    # Example: "ENTREGA REALIZADA NORMALMENTE" should match codes with "entrega"
                    # Strategy: Multi-level matching for maximum compatibility
                    occurrence_code = {}
                    best_match_score = 0
                    
                    # Clean status text (remove extra info like "(SSW WebAPI Parceiro)")
                    status_text_clean = re.sub(r'\s*\(.*?\)\s*\.?$', '', status_text).strip()
                    status_text_upper = status_text_clean.upper()
                    
                    # Extract significant words (ignore common words)
                    status_words = set(re.findall(r'\b\w+\b', status_text_upper))
                    ignore_words = {'DE', 'DA', 'DO', 'PARA', 'COM', 'SEM', 'POR', 'AO', 'A', 'O', 'E'}
                    status_keywords = status_words - ignore_words
                    
                    # Sort by description length (descending) to check longer/more specific matches first
                    sorted_codes = sorted(
                        occurrence_codes, 
                        key=lambda x: len(x["description"]), 
                        reverse=True
                    )
                    
                    for code in sorted_codes:
                        description_upper = code["description"].upper()
                        
                        # Level 1: Exact substring match (highest priority)
                        if description_upper in status_text_upper:
                            match_score = len(description_upper) * 100  # Highest score
                        elif status_text_upper in description_upper:
                            match_score = len(status_text_upper) * 100
                        else:
                            # Level 2: Word-based matching (check keyword overlap)
                            desc_words = set(re.findall(r'\b\w+\b', description_upper))
                            desc_keywords = desc_words - ignore_words
                            
                            # Calculate overlap
                            common_words = status_keywords & desc_keywords
                            
                            if common_words:
                                # Score based on number of matching words and their length
                                match_score = sum(len(word) for word in common_words)
                            else:
                                match_score = 0
                        
                        # Keep the best match
                        if match_score > best_match_score:
                            occurrence_code = code
                            best_match_score = match_score
                    
                    # Map occurrence to shipment status
                    # Use 'process' as primary indicator for finalization
                    event_status = "in_transit"  # default
                    if occurrence_code:
                        occ_type = occurrence_code.get("type", "").lower()
                        occ_process = occurrence_code.get("process", "").lower()
                        
                        # Priority 1: Check 'process' for finalization indicators
                        if occ_process == "entrega":
                            # Entrega process = delivered (even if type is "pendência transportadora")
                            event_status = "delivered"
                        elif occ_process == "finalizadora":
                            # Finalizadora process = also delivered/finalized
                            event_status = "delivered"
                        elif occ_process == "devolução":
                            # Return to sender
                            event_status = "returned"
                        
                        # Priority 2: Check 'type' for specific cases
                        elif occ_type == "baixa":
                            event_status = "cancelled"
                        elif occ_type == "préentrega":
                            event_status = "out_for_delivery"
                        
                        # Priority 3: Delivery attempts and holding
                        elif occ_process == "reentrega":
                            event_status = "failed_delivery"
                        elif occ_process == "agendamento":
                            event_status = "awaiting_pickup"
                        elif "pendência" in occ_type:
                            event_status = "held"
                        
                        # Priority 4: Operational/informative events
                        elif occ_process in ["operacional", "coleta", "geral"]:
                            event_status = "in_transit"
                        elif occ_type == "informativa":
                            event_status = "in_transit"
                    
                    events.append(
                        {
                            "occurrence_code": occurrence_code.get("code", ""),
                            "status": event_status,
                            "description": occurrence_code.get("description", ""),
                            "location": location,
                            "unit": unit,
                            "occurred_at": occurred_at.isoformat(),
                        }
                    )

        if events:
            # Get current status (most recent event)
            current_status = events[0]["status"] if events else "pending"

            return {
                "tracking_code": None,  # SSW doesn't provide tracking code in this view
                "invoice_number": invoice_number,
                "document": cnpj,
                "carrier": "SSW",
                "current_status": current_status,
                "events": events,
                "last_update": datetime.now().isoformat(),
            }
        else:
            # No tracking paragraphs found - might be invalid NF or not yet in system
            print(f"  ℹ️  No tracking events found in HTML for {invoice_number}")
            return None

    except Exception as e:
        print(f"  ❌ Error scraping tracking for {cnpj}/{invoice_number}: {e}")
        return None


@task
def update_tracking_via_api(tracking_data: dict) -> dict:
    """
    Send tracking data to API using the tracking-updates endpoint
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{API_BASE_URL}/tracking-updates/shipment",
                json=tracking_data,
                headers={"X-API-Key": API_KEY},
            )

            # Log response for debugging
            if response.status_code != 200:
                print(f"  ⚠️ API returned status {response.status_code}")
                print(f"  Response: {response.text[:500]}")

            response.raise_for_status()
            result = response.json()

        return {
            "success": True,
            "invoice_number": tracking_data["invoice_number"],
            "result": result,
        }

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if hasattr(e.response, "text") else str(e)
        print(f"  ❌ HTTP Error: {e.response.status_code}")
        print(f"  Detail: {error_detail[:500]}")
        return {
            "success": False,
            "invoice_number": tracking_data["invoice_number"],
            "error": f"HTTP {e.response.status_code}: {error_detail[:200]}",
        }
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        return {
            "success": False,
            "invoice_number": tracking_data["invoice_number"],
            "error": str(e),
        }


@task
def get_pending_shipments() -> list[dict]:
    """
    Fetch pending shipments from API using API Key authentication
    Uses the new /tracking-updates/pending-shipments endpoint
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{API_BASE_URL}/tracking-updates/pending-shipments",
                headers={"X-API-Key": API_KEY},
                params={"limit": 100},
            )

            if response.status_code != 200:
                print(f"⚠️ API returned status {response.status_code}")
                print(f"Response: {response.text[:500]}")

            response.raise_for_status()
            shipments = response.json()

        # Extract required data
        pending = []
        for shipment in shipments:
            pending.append(
                {
                    "cnpj": shipment["document"],
                    "invoice_number": shipment["invoice_number"],
                }
            )

        return pending

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error fetching pending shipments: {e.response.status_code}")
        print(f"Detail: {e.response.text[:500]}")
        return []
    except Exception as e:
        print(f"❌ Error fetching pending shipments: {e}")
        return []


@flow(name="sync_ssw_tracking")
def sync_ssw_tracking():
    """
    Main flow to sync SSW tracking data
    1. Fetch occurrence codes from API (once)
    2. Fetch pending shipments from API
    3. Scrape tracking data from SSW for each shipment
    4. Update API with new tracking data
    """
    print("🚀 Starting SSW tracking sync...")

    # Fetch occurrence codes once (used by all shipments)
    print("📋 Fetching occurrence codes...")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{API_BASE_URL}/tracking-updates/occurrence-codes",
                headers={"X-API-Key": API_KEY},
            )
            if response.status_code != 200:
                print(f"⚠️ API returned status {response.status_code}")
                print(f"Response: {response.text[:500]}")
            response.raise_for_status()
            occurrence_codes = response.json()
            print(f"✓ Loaded {len(occurrence_codes)} occurrence codes")
    except Exception as e:
        print(f"❌ Failed to fetch occurrence codes: {e}")
        return []

    # Get pending shipments
    pending_shipments = get_pending_shipments()
    print(f"📦 Found {len(pending_shipments)} pending shipments")

    if not pending_shipments:
        print("✅ No pending shipments to process")
        return []

    results = []

    # Process each shipment
    for shipment in pending_shipments:
        print(f"\n📍 Processing {shipment['invoice_number']}...")

        # Scrape tracking data
        tracking_data = scrape_ssw_tracking(
            cnpj=shipment["cnpj"], 
            invoice_number=shipment["invoice_number"],
            occurrence_codes=occurrence_codes
        )

        if tracking_data:
            print(f"  ✓ Found {len(tracking_data['events'])} tracking events")

            # Update API
            result = update_tracking_via_api(tracking_data)
            results.append(result)

            if result["success"]:
                print("  ✓ Successfully updated API")
            else:
                print(f"  ✗ Failed to update API: {result.get('error')}")
        else:
            print("  ✗ No tracking data found")
            results.append(
                {
                    "success": False,
                    "invoice_number": shipment["invoice_number"],
                    "error": "No tracking data found",
                }
            )

    # Summary
    successful = sum(1 for r in results if r["success"])
    no_data = sum(
        1
        for r in results
        if not r["success"] and "No tracking data found" in r.get("error", "")
    )
    failed = len(results) - successful - no_data

    print(f"\n{'='*50}")
    print(f"✅ Successfully updated: {successful}")
    if no_data > 0:
        print(f"⚠️  No tracking data found: {no_data}")
    if failed > 0:
        print(f"❌ Failed (errors): {failed}")
    print(f"📊 Total processed: {len(results)}")
    print(f"{'='*50}")

    return results


if __name__ == "__main__":
    # Run the flow
    sync_ssw_tracking()

    # To deploy as a scheduled flow:
    # sync_ssw_tracking.serve(
    #     name="ssw_tracking_sync",
    #     cron="*/60 * * * *"  # Every 60 minutes
    # )
