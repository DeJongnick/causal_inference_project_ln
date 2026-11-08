# IRA & CHIPS Act : ont-ils causé le boom de l'investissement industriel américain ?

Projet du cours *Causal Inference & Experimentation* (Albert School).

## Contexte

En août 2022, les États-Unis adoptent deux lois de politique industrielle majeures.

- Le CHIPS and Science Act (9 août 2022) prévoit environ 52 Md$ de subventions et de crédits d'impôt pour relocaliser la production de semi-conducteurs.
- L'Inflation Reduction Act, ou IRA (16 août 2022), accorde des crédits d'impôt massifs aux énergies propres et à leur chaîne de fabrication (batteries, solaire, véhicules électriques, hydrogène).

Dans les mois qui suivent, les dépenses de construction d'usines aux États-Unis explosent. La construction dans l'électronique et l'équipement électrique passe d'environ 8 Md$ (rythme annuel) début 2021 à plus de 120 Md$ mi-2024.

## Question de recherche

> Quelle part de ce boom est causalement attribuable à l'IRA et au CHIPS Act ?

Le boom coïncide avec d'autres facteurs : le reshoring post-COVID, les tensions sur les chaînes d'approvisionnement, l'inflation des coûts de construction et la hausse des taux de la Fed. L'objectif est d'isoler l'effet propre des lois en construisant un contrefactuel, c'est-à-dire ce qui se serait passé sans elles.

## Approche

Le projet combine deux méthodes.

1. Un Difference-in-Differences compare, avant et après août 2022, la construction d'usines électronique et électrique, directement visée par les lois, aux autres sous-secteurs manufacturiers (`ntb/did.ipynb`).
2. Un synthetic control construit des États-Unis synthétiques à partir d'une combinaison de pays de l'OCDE qui reproduit la trajectoire américaine avant 2022. L'écart après 2022 mesure l'effet des lois à l'échelle du pays (`ntb/synthetic_control.ipynb`).

Des placebos (fausses dates, secteurs ou pays non traités) servent à l'inférence et aux tests de robustesse. L'analyse exploratoire est dans `ntb/eda.ipynb`.

## Enjeux

Le sujet se lit aussi du point de vue d'un investisseur (private equity, infrastructure). Il s'agit de savoir quels secteurs et quels États ont capté le capital, et si la politique publique a créé de l'investissement ou seulement déplacé des projets qui auraient eu lieu de toute façon. Le ralentissement observé à partir de 2025, avec la remise en cause de certains crédits, pose aussi la question de la durabilité du boom et offre un second événement à étudier.

## Données

Toutes les données sont publiques : Census Bureau, FRED, OCDE et Clean Investment Monitor. Leur description détaillée est dans [`data/README.md`](data/README.md).
