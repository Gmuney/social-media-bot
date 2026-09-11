import asyncio
import os
import sys

import requests
from dotenv import load_dotenv
from nostr_sdk import Client, EventBuilder, Keys, Kind, KindStandard, RelayUrl

load_dotenv()

RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]

LINKEDIN_VERSION = "202608"


async def post_to_nostr(message: str) -> None:
    nsec = os.getenv("NOSTR_NSEC", "").strip()
    if not nsec or nsec.startswith("nsec1..."):
        print("[Nostr] Skipped: add your nsec to .env as NOSTR_NSEC")
        return

    keys = Keys.parse(nsec)
    client = Client()

    for relay in RELAYS:
        await client.add_relay(RelayUrl.parse(relay))
    await client.connect()

    kind = Kind.from_std(KindStandard.TEXT_NOTE)
    event = EventBuilder(kind, message).finalize(keys)
    await client.send_event(event)
    print(f"[Nostr] Published {event.id().to_bech32()}")

    await client.shutdown()


def linkedin_person_urn(token: str) -> str | None:
    urn = os.getenv("LINKEDIN_PERSON_URN", "").strip()
    if urn:
        return urn

    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if response.status_code != 200:
        print(f"[LinkedIn] Could not look up profile: {response.status_code} {response.text}")
        return None

    member_id = response.json().get("sub")
    if not member_id:
        print("[LinkedIn] userinfo did not include a member id")
        return None

    return f"urn:li:person:{member_id}"


def post_to_linkedin(message: str) -> None:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        print("[LinkedIn] Skipped: add LINKEDIN_ACCESS_TOKEN to .env")
        return

    try:
        author = linkedin_person_urn(token)
        if not author:
            return

        response = requests.post(
            "https://api.linkedin.com/rest/posts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Linkedin-Version": LINKEDIN_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json={
                "author": author,
                "commentary": message,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
            timeout=30,
        )
        if response.status_code in (200, 201):
            post_id = response.headers.get("x-restli-id", "post")
            print(f"[LinkedIn] Published {post_id}")
        else:
            print(f"[LinkedIn] Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[LinkedIn] Error: {e}")


async def main() -> None:
    message = " ".join(sys.argv[1:]).strip() or "Hello from the social media bot."
    print(f"Broadcasting: {message}")
    await post_to_nostr(message)
    post_to_linkedin(message)


if __name__ == "__main__":
    asyncio.run(main())
