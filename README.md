# IRA & CHIPS Act : ont-ils causé le boom de l'investissement industriel américain ?

Projet du cours *Causal Inference & Experimentation* (Albert School).

## Contexte

En août 2022, les États-Unis adoptent deux lois de politique industrielle majeures :

- **CHIPS and Science Act** (9 août 2022) : environ 52 Md$ de subventions et crédits d'impôt pour relocaliser la production de semi-conducteurs.
- **Inflation Reduction Act – IRA** (16 août 2022) : des crédits d'impôt massifs pour les énergies propres et leur chaîne de fabrication (batteries, solaire, véhicules électriques, hydrogène…).

Dans les mois qui suivent, les dépenses de construction d'usines aux États-Unis explosent. La construction dans l'électronique et l'électrique passe d'environ 8 Md$ (rythme annuel) début 2021 à plus de 120 Md$ mi-2024.

## Question de recherche

> **Quelle part de ce boom est causalement attribuable à l'IRA et au CHIPS Act ?**

Corrélation n'est pas causalité. Le boom coïncide avec d'autres facteurs : le reshoring post-COVID, les tensions sur les chaînes d'approvisionnement, l'inflation des coûts de construction et la hausse des taux de la Fed. L'objectif est d'isoler l'effet propre des lois en construisant un **contrefactuel** : que se serait-il passé sans elles ?

## Approche

Le projet applique deux méthodes vues en cours :

1. **Difference-in-Differences.** On compare, avant et après août 2022, les secteurs ciblés par les lois (construction manufacturière electronic/electrical, clean tech) aux secteurs peu ou pas ciblés (chimie, agroalimentaire, bureaux, commerces).
2. **Synthetic Control.** On construit des « États-Unis synthétiques » à partir d'une combinaison de pays de l'OCDE qui reproduit la trajectoire américaine avant 2022. L'écart après 2022 mesure l'effet des lois.

Les placebo tests (dates fictives, pays ou secteurs non traités) servent d'inférence et de tests de robustesse.

## Pourquoi c'est intéressant

Le sujet se lit aussi avec une logique d'investisseur (private equity, infrastructure) :

- **Où va le capital ?** Quels secteurs et quels États ont capté l'investissement ?
- **La politique publique crée-t-elle de la valeur ou déplace-t-elle seulement des projets qui auraient eu lieu de toute façon ?**
- **Ce boom est-il durable ?** Le ralentissement observé à partir de 2025, avec la remise en cause de certains crédits, offre un second événement à analyser.

## Données

Toutes les données sont publiques : Census Bureau, FRED, OCDE et Clean Investment Monitor. Leur description détaillée est dans [`data/README.md`](data/README.md).
