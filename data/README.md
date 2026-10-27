# Données du projet

Tous les fichiers sont dans `raw/`. Ce sont des données publiques, téléchargées le 26 octobre 2026 et non modifiées (seulement mises en forme en CSV).

**Date du traitement :** août 2022 (CHIPS Act le 9 août, IRA le 16 août).

## Vue d'ensemble

| Fichier | Source | Fréquence | Période | Rôle dans le projet |
|---|---|---|---|---|
| `census_private_construction_spending_monthly.csv` | US Census Bureau | Mensuelle | 2010-01 → 2026-08 | **Outcome principal**, DiD entre secteurs |
| `fred_macro_industry_monthly.csv` | FRED (St. Louis Fed) | Mensuelle | 2010-01 → 2026-09 | Déflateur, confounders, effets en aval |
| `oecd_gfcf_other_structures_quarterly.csv` | OCDE | Trimestrielle | 2010-Q1 → 2026-Q2 | **Synthetic control**, États-Unis vs autres pays |
| `cim_us_clean_investment_quarterly.csv` | Clean Investment Monitor | Trimestrielle | 2018-Q1 → 2026-Q2 | Investissement clean tech par technologie |
| `cim_state_investment_share_gdp.csv` | Clean Investment Monitor | Coupe transversale | 4 derniers trimestres | Exposition des États |

---

## 1. Census : dépenses de construction privée

`census_private_construction_spending_monthly.csv`

**Ce que ça mesure :** la valeur des travaux de construction privée réalisés chaque mois aux États-Unis (*Value of Construction Put in Place*). C'est de l'investissement effectivement dépensé, pas des projets annoncés.

**Unité :** millions de dollars courants, en taux annuel désaisonnalisé (SAAR). Une valeur de 120 000 signifie « au rythme de ce mois, 120 milliards sur un an ».

**Source :** fichier `privsatime.xlsx` sur https://www.census.gov/construction/c30/historical_data.html

| Colonne | Description |
|---|---|
| `date` | Premier jour du mois |
| `flag` | `p` = préliminaire, `r` = révisé (les derniers mois peuvent encore bouger) |
| `nonresidential` | Total de la construction non résidentielle privée |
| `office`, `data_center` | Bureaux, dont data centers (data centers à partir de 2014) |
| `commercial`, `warehouse` | Commerce, dont entrepôts |
| `health_care`, `educational` | Santé, éducation |
| `power`, `electric` | Énergie, dont électricité |
| `manufacturing` | Total de la construction manufacturière |
| `mfg_computer_electronic_electrical` | **Groupe traité principal** : usines de semi-conducteurs, d'électronique, de batteries… |
| `mfg_chemical`, `mfg_food_bev_tobacco`, `mfg_plastic_rubber`, `mfg_nonmetallic_mineral`, `mfg_fabricated_metal`, `mfg_transportation_equipment` | Autres sous-secteurs manufacturiers, **groupes de contrôle potentiels** |

**Usage :** DiD. On compare `mfg_computer_electronic_electrical` aux autres sous-secteurs, avant et après août 2022.

**À faire avant l'analyse :** déflater avec `WPUSI012011` du fichier FRED, car les montants sont nominaux et les coûts de construction ont fortement augmenté en 2021-2022.

---

## 2. FRED : contexte macro et industriel

`fred_macro_industry_monthly.csv`

**Source :** https://fred.stlouisfed.org (une colonne = un identifiant de série FRED)

| Colonne | Description | Unité |
|---|---|---|
| `TTLCONS` | Construction totale (public + privé) | M$, SAAR |
| `TLNRESCONS` | Construction non résidentielle totale | M$, SAAR |
| `TLMFGCONS` | Construction manufacturière totale | M$, SAAR |
| `PRMFGCONS` | Construction manufacturière privée | M$, SAAR |
| `TLCOMCONS` | Construction commerciale | M$, SAAR |
| `TLOFCONS` | Construction de bureaux | M$, SAAR |
| `WPUSI012011` | Indice des prix des matériaux de construction → **déflateur** | Indice 1982 = 100 |
| `IPMAN` | Production industrielle manufacturière | Indice 2017 = 100 |
| `IPG3344S` | Production industrielle de semi-conducteurs | Indice 2017 = 100 |
| `MANEMP` | Emploi manufacturier total | Milliers |
| `CES3133400001` | Emploi : computer & electronic products | Milliers |
| `CES3133440001` | Emploi : semi-conducteurs et composants | Milliers |
| `CES3133500001` | Emploi : équipement électrique | Milliers |
| `CES3133600101` | Emploi : automobile et pièces | Milliers |
| `FEDFUNDS` | Taux directeur de la Fed | % |
| `GS10` | Taux du Treasury à 10 ans | % |

**Usages :**

- **Déflater** les dépenses de construction (`WPUSI012011`).
- **Contrôler les confounders :** la hausse des taux de 2022-2023 (`FEDFUNDS`, `GS10`) freine l'investissement au moment exact du traitement, ce qui biaise l'effet estimé vers le bas.
- **Mesurer les effets en aval :** l'investissement s'est-il traduit en production (`IPG3344S`) et en emplois (`CES…`) ?

---

## 3. OCDE : investissement en structures par pays

`oecd_gfcf_other_structures_quarterly.csv`

**Ce que ça mesure :** la formation brute de capital fixe (FBCF) en « autres bâtiments et ouvrages » (code N112G), c'est-à-dire tout le non résidentiel : usines, bureaux, infrastructures.

**Unité :** volume chaîné (corrigé de l'inflation), désaisonnalisé, en **millions de monnaie nationale** (dollars, euros, yens, couronnes…).

**Source :** OECD Quarterly National Accounts (`DSD_NAMAIN1@DF_QNA`), https://data-explorer.oecd.org

**Colonnes :** `quarter`, puis une colonne par pays (code ISO) : `USA` (le traité) et 20 pays donneurs (`AUS`, `AUT`, `CAN`, `CZE`, `DEU`, `DNK`, `ESP`, `FIN`, `FRA`, `GBR`, `IRL`, `ISR`, `ITA`, `JPN`, `NLD`, `NOR`, `NZL`, `POL`, `PRT`, `SWE`).

**Usage :** synthetic control. On pondère les pays donneurs pour reproduire la trajectoire américaine avant 2022.

**Points d'attention :**

- **Normaliser chaque pays** (par exemple indice 2019 = 100) avant toute comparaison, car les monnaies et les tailles diffèrent.
- **Mesure plus large que le Census :** N112G inclut tout le non résidentiel, donc l'effet sera dilué.
- **Donneurs eux-mêmes perturbés :** l'Europe subit la crise énergétique de 2022 et a ses propres plans (Chips Act européen).

---

## 4. Clean Investment Monitor : investissement clean tech par technologie

`cim_us_clean_investment_quarterly.csv`

**Ce que ça mesure :** l'investissement dans les technologies bas carbone aux États-Unis, au niveau national, par segment et par technologie.

**Unité :** **milliards de dollars 2024** (déjà corrigés de l'inflation).

**Source :** Rhodium Group et MIT, https://www.cleaninvestmentmonitor.org/us/database (licence CC BY 4.0). Valeurs extraites des graphiques du tableau de bord public.

**Structure des colonnes :** `<groupe>__<technologie>`

| Préfixe | Signification |
|---|---|
| `total__` | Investissement réalisé total par segment : `manufacturing`, `energy_and_industry`, `retail` |
| `mfg_actual__` / `mfg_announced__` | **Usines** clean tech (batteries, solaire, véhicules électriques, minerais critiques, éolien, électrolyseurs…), investissement réalisé ou annoncé |
| `ei_actual__` / `ei_announced__` | **Production d'énergie et décarbonation industrielle** (solaire, stockage, éolien, hydrogène, capture carbone, carburants d'aviation durables, nucléaire…) |
| `retail__` | Achats des ménages et entreprises (véhicules électriques, pompes à chaleur, solaire distribué) |

**Valeurs manquantes :** une cellule vide signifie aucune valeur ce trimestre, `NaN` une valeur non renseignée dans la source.

**Usages :**

- Montrer **quelles technologies** ont capté l'investissement après l'IRA.
- Comparer **investissement annoncé et réalisé**, l'annonce réagissant plus vite à la loi.
- Test de robustesse face au Census, mais la période avant traitement est courte (2018-2022).

---

## 5. Clean Investment Monitor : exposition des États

`cim_state_investment_share_gdp.csv`

**Ce que ça mesure :** pour chaque État, l'investissement clean tech des **4 derniers trimestres** en **% de son PIB**, par segment (`retail`, `manufacturing`, `energy_and_industry`).

**Usage :** c'est une photo à une date, pas une série temporelle. Elle sert à mesurer **l'intensité du traitement** par État, par exemple pour un DiD à traitement continu si l'on ajoute ensuite des données d'emploi par État.

---

## Comment les fichiers s'articulent

| Étape de l'analyse | Fichiers |
|---|---|
| 1. Décrire le boom | Census + FRED (`TLMFGCONS`) |
| 2. DiD entre secteurs | Census, déflaté avec `WPUSI012011` (FRED) |
| 3. Synthetic control entre pays | OCDE |
| 4. Quelles technologies ? | CIM trimestriel |
| 5. Effets en aval (production, emploi) | FRED |
| 6. Robustesse (taux, placebos) | FRED + tous les autres fichiers |

## Non inclus

Le panel État × trimestre × technologie et la base usine par usine du Clean Investment Monitor ne sont disponibles que sur **ClimateDeck** (Rhodium), avec un compte gratuit. Pour les utiliser, les télécharger manuellement et les déposer dans `raw/`.
