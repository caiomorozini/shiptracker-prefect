from dotenv import load_dotenv
from prefect import flow, task
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import Optional
import os


# API Configuration
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
API_KEY: str = os.getenv("CRONJOB_API_KEY", "")

if not API_KEY:
    raise ValueError("CRONJOB_API_KEY environment variable is required")


@task
def scrape_ssw_tracking(cnpj: str, invoice_number: str) -> Optional[dict]:
    """
    Scrape tracking data from SSW website
    Returns parsed tracking data or None if failed
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

                # Extract location
                location_match = re.findall(r"(\w+)", location_datetime)
                location = (
                    " ".join(location_match[:2]) if len(location_match) >= 2 else None
                )

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

                    # Extract status and occurrence code
                    status_parts = status_text.split("  ")
                    status = status_parts[0].strip()

                    # Extract only numeric occurrence code (2 digits)
                    occurrence_code = None
                    if len(status_parts) > 1:
                        # Try to extract numeric code (format: "01", "02", etc)
                        code_match = re.search(r"\b(\d{2})\b", status_parts[1])
                        if code_match:
                            occurrence_code = code_match.group(1)

                    events.append(
                        {
                            "occurrence_code": occurrence_code,
                            "status": status,
                            "description": status_text.strip(),
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


@flow(name="SSW Tracking Sync")
def sync_ssw_tracking():
    """
    Main flow to sync SSW tracking data
    1. Fetch pending shipments from API
    2. Scrape tracking data from SSW for each shipment
    3. Update API with new tracking data
    """
    print("🚀 Starting SSW tracking sync...")

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
            cnpj=shipment["cnpj"], invoice_number=shipment["invoice_number"]
        )

        if tracking_data:
            print(f"  ✓ Found {len(tracking_data['events'])} tracking events")

            # Update API
            result = update_tracking_via_api(tracking_data)
            results.append(result)

            if result["success"]:
                print(f"  ✓ Successfully updated API")
            else:
                print(f"  ✗ Failed to update API: {result.get('error')}")
        else:
            print(f"  ✗ No tracking data found")
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
    # sync_ssw_tracking()

    # To deploy as a scheduled flow:
    sync_ssw_tracking.serve(
        name="ssw_tracking_sync",
        cron="*/60 * * * *"  # Every 60 minutes
    )
