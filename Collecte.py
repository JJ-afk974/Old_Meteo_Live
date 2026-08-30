import requests
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta

FICHIER = "poly_live.csv"

# Géographies à récupérer
VILLES = {
    "new_york": "new-york",
    "miami": "miami",
}

# J+0 et J+1
aujourdhui = datetime.now().date()
DATES = [
    aujourdhui,
    aujourdhui + timedelta(days=1),
]


def fetch_poly(slug):
    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"

    try:
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print(f"[ERREUR] {slug} -> HTTP {r.status_code}")
            return None

        return r.json()

    except requests.RequestException as e:
        print(f"[ERREUR] {slug} -> {e}")
        return None


rows = []

for ville, ville_slug in VILLES.items():

    for date in DATES:

        # Format YYYY-MM-DD
        date_str = date.strftime("%Y-%m-%d")

        # Exemple :
        # highest-temperature-in-new-york-on-2026-08-30
        slug = f"highest-temperature-in-{ville_slug}-on-{date_str}"

        print(f"\nRécupération : {ville} | {date_str}")
        print(f"Slug : {slug}")

        event = fetch_poly(slug)

        if event is None:
            continue

        for market in event.get("markets", []):

            try:
                token_ids = json.loads(market["clobTokenIds"])
                token_yes = token_ids[0]

                book_response = requests.get(
                    "https://clob.polymarket.com/book",
                    params={"token_id": token_yes},
                    timeout=10
                )

                if book_response.status_code != 200:
                    print(
                        f"[ERREUR BOOK] {ville} | {date_str} | "
                        f"{market.get('groupItemTitle')} -> "
                        f"HTTP {book_response.status_code}"
                    )
                    continue

                book = book_response.json()

                # On conserve la logique de ton code initial
                best_bid = (
                    book["bids"][-1]
                    if book.get("bids")
                    else {"price": None, "size": None}
                )

                best_ask = (
                    book["asks"][-1]
                    if book.get("asks")
                    else {"price": None, "size": None}
                )

                rows.append({
                    "ville": ville,
                    "date": date_str,
                    "jour": "J+0" if date == aujourdhui else "J+1",
                    "slug": slug,
                    "option": market.get("groupItemTitle"),
                    "bestBid": best_bid["price"],
                    "bidVolume": best_bid["size"],
                    "bestAsk": best_ask["price"],
                    "askVolume": best_ask["size"],
                    "_collecte_le": datetime.now().isoformat(),
                })

            except Exception as e:
                print(
                    f"[ERREUR MARKET] {ville} | {date_str} | "
                    f"{market.get('groupItemTitle')} -> {e}"
                )

            # Petite pause pour éviter d'enchaîner trop rapidement les requêtes
            time.sleep(0.1)


# Création du DataFrame
data = pd.DataFrame(rows)

if not data.empty:
    data.to_csv(
        FICHIER,
        mode="a",
        header=not os.path.exists(FICHIER),
        index=False
    )

    print(f"\n{len(data)} lignes enregistrées dans {FICHIER}")

else:
    print("\nAucune donnée récupérée.")
