import requests
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta, timezone

FICHIER = "poly_live.csv"

# IMPORTANT :
# Polymarket utilise "nyc" et non "new-york"
VILLES = {
    "new_york": "nyc",
    "miami": "miami",
}

TYPES_TEMPERATURE = {
    "highest": "highest-temperature",
    "lowest": "lowest-temperature",
}

TIMEOUT = 15

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})


def make_slug(city_slug, date, temperature_type):

    month = date.strftime("%B").lower()

    return (
        f"{TYPES_TEMPERATURE[temperature_type]}"
        f"-in-{city_slug}-on-{month}-{date.day}-{date.year}"
    )


def fetch_event(slug):

    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"

    try:
        r = session.get(url, timeout=TIMEOUT)

        print(f"GET {slug} -> HTTP {r.status_code}")

        if r.status_code != 200:
            return None

        return r.json()

    except Exception as e:
        print(f"Erreur API : {e}")
        return None


def fetch_book(token_id):

    url = "https://clob.polymarket.com/book"

    try:

        r = session.get(
            url,
            params={"token_id": token_id},
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            print(
                f"BOOK HTTP {r.status_code} "
                f"token={token_id}"
            )
            return None

        return r.json()

    except Exception as e:
        print(f"Erreur book : {e}")
        return None


def best_prices(book):

    bids = book.get("bids", [])
    asks = book.get("asks", [])

    if bids:

        best_bid = max(
            bids,
            key=lambda x: float(x["price"])
        )

    else:

        best_bid = {
            "price": None,
            "size": None
        }

    if asks:

        best_ask = min(
            asks,
            key=lambda x: float(x["price"])
        )

    else:

        best_ask = {
            "price": None,
            "size": None
        }

    return best_bid, best_ask


def main():

    now = datetime.now(timezone.utc)

    # J+0
    date_j0 = now.date()

    # J+1
    date_j1 = date_j0 + timedelta(days=1)

    dates = [
        ("J+0", date_j0),
        ("J+1", date_j1),
    ]

    rows = []

    print("=" * 80)
    print("POLYMARKET TEMPERATURE COLLECTOR")
    print("=" * 80)

    for ville, city_slug in VILLES.items():

        for temperature_type in TYPES_TEMPERATURE:

            for jour, date in dates:

                slug = make_slug(
                    city_slug,
                    date,
                    temperature_type
                )

                print()
                print("-" * 80)
                print(
                    f"{ville} | "
                    f"{temperature_type} | "
                    f"{jour} | "
                    f"{date}"
                )
                print(slug)

                event = fetch_event(slug)

                if event is None:

                    print(
                        "EVENT NON TROUVE"
                    )

                    continue

                markets = event.get(
                    "markets",
                    []
                )

                print(
                    f"Markets trouvés : {len(markets)}"
                )

                if not markets:
                    continue

                collecte_le = datetime.now(
                    timezone.utc
                ).isoformat()

                for market in markets:

                    option = market.get(
                        "groupItemTitle"
                    )

                    if not option:
                        continue

                    try:

                        token_ids = json.loads(
                            market.get(
                                "clobTokenIds",
                                "[]"
                            )
                        )

                    except Exception as e:

                        print(
                            f"Erreur token IDs : {e}"
                        )

                        continue

                    if not token_ids:
                        continue

                    # YES token
                    token_yes = token_ids[0]

                    book = fetch_book(
                        token_yes
                    )

                    if book is None:
                        continue

                    bid, ask = best_prices(
                        book
                    )

                    rows.append({

                        "ville": ville,

                        "temperature_type":
                            temperature_type,

                        "jour": jour,

                        "date": str(date),

                        "slug": slug,

                        "option": option,

                        "token_yes": token_yes,

                        "bestBid":
                            bid["price"],

                        "bidVolume":
                            bid["size"],

                        "bestAsk":
                            ask["price"],

                        "askVolume":
                            ask["size"],

                        "_collecte_le":
                            collecte_le,
                    })

                    print(
                        f"  {option:15} "
                        f"bid={bid['price']} "
                        f"ask={ask['price']}"
                    )

                    time.sleep(0.1)

    # ========================================================
    # DATAFRAME
    # ========================================================

    columns = [
        "ville",
        "temperature_type",
        "jour",
        "date",
        "slug",
        "option",
        "token_yes",
        "bestBid",
        "bidVolume",
        "bestAsk",
        "askVolume",
        "_collecte_le",
    ]

    new_data = pd.DataFrame(
        rows,
        columns=columns
    )

    print()
    print("=" * 80)
    print(
        f"Nouvelles lignes : {len(new_data)}"
    )
    print("=" * 80)

    # ========================================================
    # CREATION DU CSV
    # ========================================================

    if os.path.exists(FICHIER):

        try:

            old_data = pd.read_csv(
                FICHIER
            )

            data = pd.concat(
                [
                    old_data,
                    new_data
                ],
                ignore_index=True
            )

        except Exception:

            data = new_data

    else:

        data = new_data

    # Toujours créer le fichier
    data.to_csv(
        FICHIER,
        index=False
    )

    print(
        f"CSV sauvegardé : {FICHIER}"
    )

    print(
        f"Total lignes : {len(data)}"
    )


if __name__ == "__main__":
    main()
