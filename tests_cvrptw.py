"""Cas de test : de petits exemples dont on connaît la bonne réponse à l'avance.

Chaque test vérifie qu'une fonction du code donne bien cette réponse.
Exécution : python tests_cvrptw.py    (ou : pytest tests_cvrptw.py)
Les tests 6 à 9 lisent les instances de Solomon : pip install vrplib
"""

from cvrptw_analyse_solomon import (
    OPTIMUMS_SOLOMON, calcul_cout, charger_solomon, generer_instance,
    recherche_tabou, simuler_tournee, verifier_solution,
)


def petite_instance(distances, fenetres, services, demandes=None,
                    capacite=10, nb_camions=2):
    """Instance faite à la main : dépôt 0, puis les clients 1, 2..."""
    nb_clients = len(distances) - 1
    return {"nb_clients": nb_clients, "nb_camions": nb_camions,
            "capacite": capacite,
            "demandes": demandes or [0] + [1] * nb_clients,
            "durees_service": services, "distances": distances,
            "fenetres": fenetres}


# ------------------------------------------------------------
# Tests sur des instances faites à la main
# ------------------------------------------------------------

def test_1_temps_de_livraison_compte():
    """A ouvre et ferme à 100, la livraison chez A dure 90, B est à 10 de A
    et ferme à 150. Le camion arrive chez B à 100 + 90 + 10 = 200 : trop tard."""
    distances = [[0, 100, 100], [100, 0, 10], [100, 10, 0]]
    fenetres = [(0, 1000), (100, 100), (0, 150)]
    instance = petite_instance(distances, fenetres, services=[0, 90, 0])
    assert simuler_tournee([0, 1, 2, 0], instance) is None
    # Sans les 90 de livraison, la même tournée devient possible.
    instance["durees_service"] = [0, 0, 0]
    assert simuler_tournee([0, 1, 2, 0], instance) is not None


def test_2_attente_permise():
    """B ouvre à 100 mais le camion arrive à 30 : il attend sur place,
    et la livraison commence à 100, pas avant. L'attente compte dans la durée."""
    distances = [[0, 10, 10], [10, 0, 10], [10, 10, 0]]
    fenetres = [(0, 500), (0, 20), (100, 120)]
    info = simuler_tournee([0, 1, 2, 0], petite_instance(distances, fenetres, [0, 0, 0]))
    assert info["livraisons"] == [(1, 20), (2, 100)]
    assert info["depart"] == 10 and info["retour"] == 110
    assert info["duree"] == 100            # 30 de trajet + 70 d'attente


def test_3_capacite_controlee():
    """Deux clients de demande 6, des camions de capacité 10 :
    un seul camion ne peut pas tout porter, deux camions oui."""
    distances = [[0, 10, 10], [10, 0, 10], [10, 10, 0]]
    fenetres = [(0, 500), (0, 500), (0, 500)]
    instance = petite_instance(distances, fenetres, [0, 0, 0], demandes=[0, 6, 6])
    assert not verifier_solution([[0, 1, 2, 0]], instance)
    assert verifier_solution([[0, 1, 0], [0, 2, 0]], instance)


def test_4_chaque_client_une_seule_fois():
    """Une solution qui oublie un client, puis une qui en sert un deux fois."""
    distances = [[0, 10, 10], [10, 0, 10], [10, 10, 0]]
    fenetres = [(0, 500), (0, 500), (0, 500)]
    instance = petite_instance(distances, fenetres, [0, 0, 0])
    assert not verifier_solution([[0, 1, 0]], instance)                 # 2 oublié
    assert not verifier_solution([[0, 1, 0], [0, 1, 2, 0]], instance)   # 1 servi 2 fois
    assert verifier_solution([[0, 1, 2, 0]], instance)


def test_5_arrondi_des_decimales():
    """En Python, 0.1 + 0.2 = 0.30000000000000004. Un camion qui arrive
    pile à la fermeture (0,3) ne doit pas être refusé pour autant."""
    assert 0.1 + 0.2 != 0.3
    distances = [[0, 0.1, 0.3], [0.1, 0, 0.2], [0.3, 0.2, 0]]
    fenetres = [(0, 10), (0, 0.1), (0, 0.3)]
    instance = petite_instance(distances, fenetres, [0, 0, 0])
    assert simuler_tournee([0, 1, 2, 0], instance) is not None


# ------------------------------------------------------------
# Tests sur les instances de Solomon (lecture avec vrplib)
# ------------------------------------------------------------

def test_6_lecture_solomon():
    """C101 à 25 clients : on retrouve les valeurs du fichier, et les
    distances sont tronquées à une décimale (18,68... devient 18,6)."""
    instance = charger_solomon("C101", 25)
    assert instance["nb_clients"] == 25 and instance["capacite"] == 200
    assert instance["durees_service"][0] == 0 and instance["durees_service"][1] == 90
    assert instance["fenetres"][0] == (0, 1236)
    assert instance["distances"][0][1] == 18.6
    assert instance["optimum"] == 191.3


def test_7_insertion_toujours_valide():
    """La solution de départ (insertion) est valide sur les 36 instances."""
    for nb_clients, optimums in OPTIMUMS_SOLOMON.items():
        for nom in optimums:
            instance = charger_solomon(nom, nb_clients)
            assert verifier_solution(instance["solution_depart"], instance), instance["nom"]


def test_8_duree_et_distance():
    """Durée = trajets + livraisons + attentes. Comme T_ij = d_ij dans Solomon,
    la durée vaut au moins la distance + le total des livraisons (25 x 90)."""
    instance = charger_solomon("C101", 25)
    solution = instance["solution_depart"]
    distance = calcul_cout(solution, instance, "distance")
    duree = calcul_cout(solution, instance, "duree")
    assert duree >= distance + 25 * 90 - 1e-6


def test_9_tabou_ne_degrade_jamais_le_meilleur():
    """La meilleure solution rendue est valide, jamais pire que le départ,
    et le meilleur coût ne remonte jamais au fil des itérations."""
    for instance in (charger_solomon("R101", 25), generer_instance(30, 5, graine=1)):
        resultat = recherche_tabou(instance, iterations=300, objectif="distance")
        assert verifier_solution(resultat["solution"], instance)
        assert resultat["final"] <= resultat["initial"]
        historique = resultat["historique"]
        assert all(b <= a for a, b in zip(historique, historique[1:]))


if __name__ == "__main__":
    tests = [f for nom, f in list(globals().items()) if nom.startswith("test_")]
    for test in tests:
        test()
        print("OK ", test.__name__)
    print(f"\n{len(tests)} cas de test réussis.")
