import requests
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIGURATION
# ============================================================

FICHIER = "poly_live.csv"

VILLES = {
    "new_york": "new-york",
    "miami": "miami",
}

TIMEOUT = 10


# ============================================================
# SESSION HTTP
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (GitHub Actions Polymarket collector)"
})


# ============================================================
# CONSTRUCTION DU SLUG
# ============================================================

def make_slug(city_slug, date):
    """
    Construit le slug Polymarket :

    highest-temperature-in-new-york-on-august-30-2026
    """

    month = date.strftime("%B").lower()
    day = date.day
    year = date.year

    return f"highest-temperature-in-{city_slug}-on-{month}-{day}-{year}"


# ============================================================
# RÉCUPÉRATION DE L'ÉVÉNEMENT
# ============================================================

def fetch_event(slug):
    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"

    try:
        response = session.get(url, timeout=TIMEOUT)

        if response.status_code != 200:
            print(
                f"[EVENT] HTTP {response.status_code} "
                f"pour {slug}"
            )
            return None

        return response.json()

    except requests.RequestException as e:
        print(f"[EVENT] Erreur réseau pour {slug}: {e}")
        return None

    except ValueError as e:
        print(f"[EVENT] JSON invalide pour {slug}: {e}")
        return None


# ============================================================
# RÉCUPÉRATION DU CARNET
# ============================================================

def fetch_order_book(token_id):
    url = "https://clob.polymarket.com/book"

    try:
        response = session.get(
            url,
            params={"token_id": token_id},
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            print(
                f"[BOOK] HTTP {response.status_code} "
                f"pour token {token_id}"
            )
            return None

        return response.json()

    except requests.RequestException as e:
        print(f"[BOOK] Erreur réseau pour {token_id}: {e}")
        return None

    except ValueError as e:
        print(f"[BOOK] JSON invalide pour {token_id}: {e}")
        return None


# ============================================================
# EXTRACTION DU BEST BID / BEST ASK
# ============================================================

def get_best_prices(book):
    bids = book.get("bids", [])
    asks = book.get("asks", [])

    # Sur un carnet classique :
    # best bid = prix le plus élevé
    # best ask = prix le plus faible

    if bids:
        best_bid = max(
            bids,
            key=lambda x: float(x.get("price", 0))
        )
    else:
        best_bid = {
            "price": None,
            "size": None
        }

    if asks:
        best_ask = min(
            asks,
            key=lambda x: float(x.get("price", 999))
        )
    else:
        best_ask = {
            "price": None,
            "size": None
        }

    return best_bid, best_ask


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    # Date actuelle UTC.
    # Pour un workflow exécuté régulièrement, on veut une date
    # cohérente et reproductible.
    maintenant = datetime.now(timezone.utc)

    date_j0 = maintenant.date()
    date_j1 = date_j0 + timedelta(days=1)

    dates = [
        ("J+0", date_j0),
        ("J+1", date_j1),
    ]

    rows = []

    print("=" * 70)
    print("COLLECTE POLYMARKET")
    print("=" * 70)
    print(f"Date UTC : {maintenant.isoformat()}")
    print()

    # --------------------------------------------------------
    # Boucle villes
    # --------------------------------------------------------

    for ville, ville_slug in VILLES.items():

        # ----------------------------------------------------
        # Boucle J+0 / J+1
        # ----------------------------------------------------

        for jour, date in dates:

            slug = make_slug(ville_slug, date)

            print("-" * 70)
            print(f"Ville : {ville}")
            print(f"Jour  : {jour}")
            print(f"Date  : {date}")
            print(f"Slug  : {slug}")

            # ------------------------------------------------
            # Event Polymarket
            # ------------------------------------------------

            event = fetch_event(slug)

            if event is None:
                print("Aucun événement récupéré.")
                continue

            markets = event.get("markets", [])

            if not markets:
                print("Événement trouvé mais aucun market.")
                continue

            print(f"{len(markets)} markets trouvés.")

            # Timestamp unique pour ce snapshot
            collecte_le = datetime.now(timezone.utc).isoformat()

            # ------------------------------------------------
            # Boucle markets
            # ------------------------------------------------

            for market in markets:

                option = market.get("groupItemTitle")

                if not option:
                    print("Market sans groupItemTitle, ignoré.")
                    continue

                # ------------------------------------------------
                # Tokens
                # ------------------------------------------------

                try:
                    token_ids = json.loads(
                        market.get("clobTokenIds", "[]")
                    )

                except (json.JSONDecodeError, TypeError):
                    print(
                        f"Token IDs invalides pour option "
                        f"{option}"
                    )
                    continue

                if not token_ids:
                    print(
                        f"Aucun token pour option {option}"
                    )
                    continue

                # Premier token = YES
                token_yes = token_ids[0]

                # ------------------------------------------------
                # Order book
                # ------------------------------------------------

                book = fetch_order_book(token_yes)

                if book is None:
                    continue

                best_bid, best_ask = get_best_prices(book)

                # ------------------------------------------------
                # Ligne CSV
                # ------------------------------------------------

                rows.append({
                    "ville": ville,
                    "jour": jour,
                    "date": str(date),
                    "slug": slug,
                    "option": option,
                    "token_yes": token_yes,

                    "bestBid": best_bid.get("price"),
                    "bidVolume": best_bid.get("size"),

                    "bestAsk": best_ask.get("price"),
                    "askVolume": best_ask.get("size"),

                    "_collecte_le": collecte_le,
                })

                print(
                    f"  {option} | "
                    f"bid={best_bid.get('price')} | "
                    f"ask={best_ask.get('price')}"
                )

                # Petite pause entre les appels API
                time.sleep(0.1)

    # ========================================================
    # CRÉATION / SAUVEGARDE DU CSV
    # ========================================================

    colonnes = [
        "ville",
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

    data = pd.DataFrame(rows, columns=colonnes)

    # --------------------------------------------------------
    # IMPORTANT :
    # on crée TOUJOURS le fichier, même si rows est vide.
    # Cela évite :
    #
    # fatal: pathspec 'poly_live.csv' did not match any files
    # --------------------------------------------------------

    if data.empty:

        print()
        print("=" * 70)
        print("AUCUNE DONNÉE RÉCUPÉRÉE")
        print("=" * 70)

        # Si le fichier n'existe pas encore,
        # on crée un CSV vide avec les bonnes colonnes.
        if not os.path.exists(FICHIER):
            data.to_csv(
                FICHIER,
                index=False
            )
            print(f"Fichier vide créé : {FICHIER}")
        else:
            print(
                f"{FICHIER} existe déjà, "
                "aucune modification effectuée."
            )

        return

    # ========================================================
    # AJOUT À L'HISTORIQUE
    # ========================================================

    if os.path.exists(FICHIER):

        try:
            ancien = pd.read_csv(FICHIER)

            data_final = pd.concat(
                [ancien, data],
                ignore_index=True
            )

        except Exception as e:

            print(
                f"Impossible de lire {FICHIER}: {e}"
            )

            data_final = data

    else:

        data_final = data

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    data_final.to_csv(
        FICHIER,
        index=False
    )

    print()
    print("=" * 70)
    print("COLLECTE TERMINÉE")
    print("=" * 70)
    print(f"Nouvelles lignes : {len(data)}")
    print(f"Total CSV        : {len(data_final)}")
    print(f"Fichier          : {FICHIER}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
