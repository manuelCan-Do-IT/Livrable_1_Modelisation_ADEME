# Livrable final ADEME : tournées de livraison (CVRPTW)

Groupe 1 : Sandago, Emmanuel, Thomas.

## Les fichiers

| Fichier | Contenu |
| --- | --- |
| `Grp1_Livrable_Final_CVRPTW.ipynb` | Le notebook final : modélisation, méthode, réalisation, résultats et interprétations |
| `cvrptw_analyse_solomon.py` | Le code : instances, recherche tabou, études expérimentales |
| `tests_cvrptw.py` | Les cas de test (9 petits exemples dont on connaît la réponse) |
| `instances/solomon/25, 50, 100/` | 12 instances de Solomon (2 par classe), en 25, 50 et 100 clients |
| `images/` | Les schémas du notebook |

## Installer

```
pip install vrplib matplotlib
```

## Lancer

Les cas de test :

```
python tests_cvrptw.py
```

Le code : changer la ligne `MODE = ...` en haut de la partie 5 de `cvrptw_analyse_solomon.py`, puis lancer `python cvrptw_analyse_solomon.py`.

| Mode | Ce qu'il fait | Objectif |
| --- | --- | --- |
| `demo` | Une instance générée de 30 clients | durée |
| `demo_solomon` | 3 instances de Solomon (C101, R101, RC101 à 25 clients) | distance |
| `instances` | Étude 1 : 60 instances générées (répartition, fenêtres, taille) | durée |
| `parametres` | Étude 2 : effet des paramètres de la tabou | durée |
| `grandes_tailles` | Étude 3 : 500, 1 000 et 2 000 clients générés | durée |
| `solomon` | Étude 4 : 12 instances × 3 tailles × 3 graines, gap à l'optimum publié | distance |
| `objectifs` | Étude 5 : durée ou distance, ce que l'on gagne et ce que l'on perd | les deux |

Les résultats (CSV, résumé et graphiques) sont enregistrés dans `resultats_cvrptw/`.

## Pourquoi la distance pour Solomon

Les optimums publiés sont des distances totales. Dans les instances de Solomon, le temps de trajet `T_ij` est égal à la distance `d_ij`. Minimiser la distance revient donc à minimiser le temps de trajet. Les livraisons ont une durée fixe, et seule l'attente diffère de la durée totale. L'étude 5 mesure cette différence.
