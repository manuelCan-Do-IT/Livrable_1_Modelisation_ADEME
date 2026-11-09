
from collections import deque

# =====================================================
# 1. DONNÉES DU PROBLÈME CVRPTW
# =====================================================

instance = {
    "nb_clients": 4,
    "nb_camions": 2,
    "capacite": 10,
    "depot": 0,

    # Demande de chaque client (indice 0 = dépôt)
    "demandes": [0, 3, 4, 2, 5],

    # Temps de trajet fixes en minutes
    "distances": [
        [0, 10, 15, 20, 12],
        [10, 0, 8, 12, 9],
        [15, 8, 0, 10, 7],
        [20, 12, 10, 0, 13],
        [12, 9, 7, 13, 0]
    ],

    # Fenêtres temporelles (ouverture, fermeture)
    # Horaires exprimés en minutes depuis minuit
    "fenetres": [
        (480, 1080),  # Dépôt : 8h00 - 18h00
        (540, 720),   # Client 1 : 9h00 - 12h00
        (600, 780),   # Client 2 : 10h00 - 13h00
        (480, 660),   # Client 3 : 8h00 - 11h00
        (660, 900)    # Client 4 : 11h00 - 15h00
    ],

    # Durées de service nulles (hypothèse retenue)
    "durees_service": [0, 0, 0, 0, 0]
}


# =====================================================
# 2. PARAMÈTRES DE LA RECHERCHE TABOU
# =====================================================

parametres_tabou = {
    "taille_tabou": 10,
    "iter_max": 100,
    "type_voisinage": "swap"
}


# =====================================================
# 3. CALCUL DU COÛT
# =====================================================

def calcul_cout(solution, instance):
    """
    Calcule la somme des durées des tournées.

    Durée d'une tournée :
    heure de retour - heure de départ

    Prend en compte :
    - Les temps de trajet
    - Les temps d'attente
    """

    cout_total = 0

    # À COMPLÉTER :
    # Pour chaque tournée :
    # 1. Déterminer son heure de départ
    # 2. Simuler les trajets et les attentes
    # 3. Déterminer son heure de retour
    # 4. Ajouter sa durée au coût total

    return cout_total


# =====================================================
# 4. VÉRIFICATION DES CAPACITÉS
# =====================================================

def verifier_capacite(solution, instance):
    """
    Vérifie que chaque camion respecte sa capacité.
    """

    capacite = instance["capacite"]
    demandes = instance["demandes"]

    # À COMPLÉTER :
    # Calculer la charge de chaque tournée
    # Retourner False si une capacité est dépassée

    pass


# =====================================================
# 5. VÉRIFICATION DES FENÊTRES TEMPORELLES
# =====================================================

def verifier_fenetres(solution, instance):
    """
    Vérifie les fenêtres temporelles de chaque client.

    Si un camion arrive avant l'ouverture :
    il attend.

    S'il arrive après la fermeture :
    la tournée est invalide.
    """

    fenetres = instance["fenetres"]
    distances = instance["distances"]

    # À COMPLÉTER :
    # Pour chaque tournée :
    # 1. Déterminer son heure de départ
    # 2. Initialiser l'heure actuelle
    # 3. Parcourir les clients dans l'ordre
    # 4. Calculer l'heure d'arrivée
    # 5. Attendre si nécessaire
    # 6. Vérifier la fermeture des fenêtres
    # 7. Vérifier le retour au dépôt

    pass


# =====================================================
# 6. VÉRIFICATION DE LA SOLUTION
# =====================================================

def verifier_solution(solution, instance):
    """
    Vérifie :
    - Le nombre maximal de camions
    - Le départ et le retour au dépôt
    - La visite unique de chaque client
    - Les capacités
    - Les fenêtres temporelles
    """

    # À COMPLÉTER :
    # Vérifier la structure des tournées

    # À COMPLÉTER :
    # Vérifier que tous les clients sont livrés
    # exactement une fois

    # À COMPLÉTER :
    # Appeler verifier_capacite()

    # À COMPLÉTER :
    # Appeler verifier_fenetres()

    pass


# =====================================================
# 7. GÉNÉRATION D'UNE SOLUTION INITIALE
# =====================================================

def solution_initiale(instance):
    """
    Construit une première solution CVRPTW valide.

    Méthode possible : construction gloutonne.
    """

    solution = []

    # À COMPLÉTER :
    # Répartir les clients entre les camions
    # Respecter les capacités
    # Respecter les fenêtres temporelles
    # Respecter le nombre de camions
    # Ajouter le dépôt au début et à la fin

    return solution


# =====================================================
# 8. GÉNÉRATION DU VOISINAGE
# =====================================================

def voisinage(solution, instance, type_voisinage):
    """
    Génère des solutions voisines.

    SWAP : échange deux clients dans une même
    tournée ou entre deux tournées.
    """

    voisins = []

    # À COMPLÉTER :
    # Générer des voisins par SWAP
    # Vérifier les capacités
    # Vérifier les fenêtres temporelles
    # Conserver les solutions valides

    return voisins


# =====================================================
# 9. RECHERCHE TABOU
# =====================================================

def recherche_tabou(instance, parametres_tabou):

    taille_tabou = parametres_tabou["taille_tabou"]
    iter_max = parametres_tabou["iter_max"]
    type_voisinage = parametres_tabou["type_voisinage"]

    # Création de la liste tabou
    liste_tabou = deque(maxlen=taille_tabou)

    # Génération de la solution initiale
    solution_depart = solution_initiale(instance)

    solution_courante = solution_depart
    meilleure_globale = solution_depart

    valeur_meilleure_globale = calcul_cout(
        solution_depart, instance
    )

    nb_iter = 0

    while nb_iter < iter_max:

        valeur_meilleure = float("inf")
        meilleure = None

        # Génération des voisins
        for voisin in voisinage(
            solution_courante,
            instance,
            type_voisinage
        ):

            # À COMPLÉTER :
            # Vérifier que le voisin n'est pas tabou
            # Calculer son coût
            # Conserver le meilleur voisin admissible

            pass

        if meilleure is None:
            break

        # À COMPLÉTER :
        # Mettre à jour la meilleure solution globale

        # À COMPLÉTER :
        # Mettre à jour la solution courante

        # À COMPLÉTER :
        # Ajouter le mouvement ou la solution
        # à la liste tabou

        # À COMPLÉTER :
        # Mettre à jour nb_iter

        pass

    return meilleure_globale


# =====================================================
# 10. EXÉCUTION DU PROGRAMME
# =====================================================

# À activer une fois les fonctions terminées

# resultat = recherche_tabou(instance, parametres_tabou)
#
# print("Meilleure solution :", resultat)
# print("Coût total :", calcul_cout(resultat, instance))
