# Format des traces (v1)

Toute l'évaluation (E1 à E5) et la visualisation (#38) se calculent a posteriori sur ces traces : un événement absent ici ne pourra pas être mesuré plus tard sans relancer les campagnes.

Décisions appliquées : T12 (lignes JSON), T11 (relecture en Python avec pandas), D8 (la disponibilité réelle n'est jamais lue par le protocole).

Fichiers associés :

- [evaluation/traces.py](../evaluation/traces.py) : schéma, chargement pandas, validation ;
- [evaluation/exemples/trace-exemple.jsonl](../evaluation/exemples/trace-exemple.jsonl) : trace d'exemple qui contient chaque type d'événement au moins une fois.

## 1. Principes

- **Un fichier par exécution** : `trace.jsonl`, ou `trace.jsonl.gz` (pandas décompresse seul). Une ligne = un objet JSON = un événement, en UTF-8, sans ligne vide.
- **Ordre** : les lignes sont écrites dans l'ordre d'exécution, donc `t` ne décroît jamais. En réseau réel (un fichier par processus), on fusionne les fichiers par un tri stable sur `t`.
- **Bornes** : la première ligne est `run_start`, la dernière `run_end`. Une trace sans `run_end` est une exécution interrompue.
- **Déterminisme** : même graine, même trace, octet pour octet (#12). Aucune valeur ne dépend de l'horloge murale ni de l'ordre d'itération d'une table de hachage. C'est pourquoi un coût est noté en nombre d'opérations, jamais en temps CPU.
- **Séparation (D8)** : `run_start`, `device`, `churn` et `run_end` sont écrits par le banc d'essai (`crates/testbed`) et par lui seul. Les crates du protocole écrivent tous les autres événements, et aucun crate du protocole ne lit une trace.
- **Aucun contenu sensible** : ni clé, ni clair, ni données de chunk. Les messages sont désignés par une empreinte (`mid`, §3).
- **Version** : `run_start.v` vaut 1. Ajouter un champ facultatif ne change pas la version. Renommer ou retirer un champ, ou en changer le sens, l'incrémente : on met alors à jour ce document, `evaluation/traces.py` et la trace d'exemple dans la même PR.

## 2. Champs communs

| Champ | Type | Sens |
|---|---|---|
| `t` | entier ≥ 0 | temps virtuel en millisecondes depuis le début de l'exécution |
| `node` | entier, ou `null` | appareil qui écrit l'événement ; `null` seulement pour `run_start` et `run_end` |
| `ev` | chaîne | type de l'événement (§4) |

Le tour i d'un événement se déduit de `t` : i = ⌊t / `params.T_ms`⌋.

## 3. Conventions de valeurs

| Valeur | Représentation |
|---|---|
| Appareil | entier attribué par le banc d'essai (0 à N − 1). Si O12 retient un identifiant dérivé de la clé, l'événement `device` donnera la correspondance |
| `did` | δ.ID en hexadécimal minuscule ; identifie le fichier et le canal |
| `mid` | empreinte d'un message tel qu'il passe sur un lien : les 16 premiers caractères hexadécimaux du SHA-256 des octets envoyés |
| `dir` | `"fwd"` : route aller (Alice → Bob, chunks) ; `"bwd"` : route retour (Bob → Alice, ACK) |
| `pos` | rang de la couche dans la route, de 1 à 4 ; 4 est l'e-squad du destinataire |
| Durées, tailles | millisecondes (suffixe `_ms`), octets |
| Probabilités | flottants dans [0, 1] |

**Le `mid` permet de reconstituer le chemin d'un message sans rien ajouter au protocole.** Un relais note le `mid` du message reçu et celui du message qu'il réémet (`relay_recv.mid` → `relay_recv.out`), et chaque saut porte le `mid` des octets envoyés. On chaîne donc `chunk_sent` → `hop` → `relay_recv` → `hop` → … → `esquad_rx`. Un même message essayé sur plusieurs membres d'une couche garde son `mid`. Un renvoi est rechiffré : il a un `mid` différent.

## 4. Événements

| `ev` | Écrit par | Rôle |
|---|---|---|
| `run_start` | banc | paramètres de l'exécution |
| `device` | banc | déclaration d'un appareil et de son utilisateur |
| `churn` | banc | changement de disponibilité réelle (X_réel) |
| `run_end` | banc | fin normale de l'exécution |
| `interaction` | e-squad | interaction USE, UL ou DL émise par l'appareil |
| `interaction_learned` | e-squad | interaction d'un autre appareil apprise par gossip (niveau détaillé) |
| `descriptor_published` | prédiction | descripteur publié dans le RPS avec p(d) |
| `channel_offer` | routes | message hors bande n° 1 produit (Alice) |
| `channel_accept` | routes | message hors bande n° 2 produit (Bob) |
| `layer_built` | routes | couche construite (PickLayer, ou e-squad) |
| `route_ready` | routes | route complète à 4 couches |
| `hop` | relais | tentative d'envoi vers un nœud, et son issue |
| `relay_recv` | relais | message reçu et déchiffré par un nœud |
| `drop` | relais | abandon : tous les membres de la couche suivante ont échoué |
| `esquad_rx` | e-squad | charge utile reçue en dernière couche, et ce qu'en fait l'appareil |
| `cache` | e-squad | opération sur le cache de l'e-squad |
| `transfer_start` | transfert | premier usage du canal par l'émetteur |
| `chunk_sent` | transfert | chunk émis ou renvoyé |
| `chunk_recv` | transfert | chunk reçu et vérifié contre δ par l'appareil récepteur |
| `ack_sent` | transfert | ACK émis |
| `ack_recv` | transfert | ACK reçu par l'émetteur |
| `transfer_end` | transfert | fin du transfert, côté émetteur ou récepteur |

Tous les champs listés ci-dessous sont obligatoires. Ceux qui peuvent être `null` le disent.

### 4.1 Banc d'essai

**`run_start`** (`node` = `null`)

| Champ | Type | Sens |
|---|---|---|
| `v` | entier | version du format (1) |
| `seed` | entier | graine de l'exécution |
| `params` | objet | paramètres de l'exécution ; seul `T_ms` (période d'un tour) est obligatoire |

Clés attendues dans `params`, pour que le lanceur de campagnes (#32) range les traces par configuration : `label`, `T_ms`, `users`, `devices_per_user`, `model`, `mu`, `eps`, `l_max`, `l_v`, `file_size`, `chunk_size`, `window`, `rto_ms`, `dead_ms`, `hop_timeout_ms`, `delta_ms` (délai Δ entre création et usage, E5). On en ajoute librement.

**`device`** : `user` (entier), l'utilisateur, donc l'e-squad, auquel appartient l'appareil. Un `device` par appareil, avant tout autre événement qui le cite.

**`churn`** : `online` (booléen). Un événement par appareil à t = 0 (état initial), puis un à chaque changement. C'est X_réel : X_réel(d, i) est l'état de d au début du tour i. Le protocole ne le lit jamais (D8).

**`run_end`** (`node` = `null`) : aucun champ.

### 4.2 E-squad et prédiction

**`interaction`**

| Champ | Type | Sens |
|---|---|---|
| `typ` | `"USE"`, `"UL"`, `"DL"` | type de l'interaction |
| `did` | hex ou `null` | δ.ID pour UL et DL ; `null` pour USE |

UL et DL sont émis à la création du canal (D13).

**`interaction_learned`** (niveau détaillé, activable par configuration) : `origin` (appareil qui a émis l'interaction), `ts` (son horodatage, en ms), `typ`. Sert à mesurer la vitesse de convergence du gossip (O8, #27).

**`descriptor_published`**

| Champ | Type | Sens |
|---|---|---|
| `round` | entier | tour i de la prédiction |
| `p` | flottant | P_i(d) publié |
| `fallback` | booléen | vrai si l'état courant n'avait jamais été vu (repli du prédicteur) |

**`esquad_rx`** : écrit par un appareil de l'e-squad qui reçoit un chunk ou un ACK, soit en dernière couche d'une route, soit d'un autre membre de son e-squad.

| Champ | Type | Sens |
|---|---|---|
| `did`, `kind`, `idx` | hex, `"chunk"`/`"ack"`, entier | message concerné |
| `mid` | hex | message par lequel il est arrivé |
| `via` | `"route"`, `"esquad"` | dernière couche d'une route, ou retransmission interne |
| `action` | `"local"`, `"forward"`, `"cache"`, `"drop"` | remis au transfert de cet appareil ; transmis à l'appareil visé ; gardé ; jeté |
| `reason` | chaîne ou `null` | pour `cache` : `"offline"`, `"unknown_did"` ; pour `drop` : `"duplicate"`, `"bad_hash"`, `"unknown_did"` ; `null` sinon |

**`cache`** : `did`, `kind`, `idx`, `op` (`"put"`, `"deliver"`, `"evict"`, `"expire"`), `entries` (nombre d'entrées du cache après l'opération). Un `esquad_rx` d'action `cache` est suivi d'un `cache` `put`. `deliver` est suivi du `hop` interne vers l'appareil visé.

### 4.3 Canaux et routes

**`channel_offer`** (Alice) : `did`, `size`, `chunk_size`, `chunks`, `oob_bytes` (taille codée du message hors bande n° 1).

**`channel_accept`** (Bob) : `did`, `oob_bytes` (taille du message n° 2).

**`layer_built`** : écrit par l'appareil qui construit la couche. Alice écrit BL3, BL4, FL1 et FL2 ; Bob écrit FL3, FL4, BL1 et BL2. La date de l'événement dit quand les couches de tête ont été tirées (O2).

| Champ | Type | Sens |
|---|---|---|
| `did`, `dir`, `pos` | | couche concernée |
| `members` | liste d'entiers | membres, dans l'ordre de la couche |
| `p` | liste de flottants ou `null` | p(d) utilisés, dans le même ordre (`null` si inconnu) |
| `unavail` | flottant ou `null` | indisponibilité prédite ∏(1 − p) |
| `stop` | `"eps"`, `"lmax"`, `"view"`, `"esquad"` | arrêt de PickLayer : ε atteint, L_max atteint, vue épuisée ; `"esquad"` pour la couche 4, qui n'est pas tirée |
| `view` | entier ou `null` | nombre de candidats dans la vue au moment du tirage ; `null` pour la couche 4 |

**`route_ready`** : `did`, `dir`, `sizes` (taille des 4 couches). Alice l'écrit pour `fwd`, Bob pour `bwd`.

### 4.4 Relayage

**`hop`** : une tentative d'envoi, écrite par l'expéditeur du saut (source, relais ou membre d'e-squad).

| Champ | Type | Sens |
|---|---|---|
| `to` | entier | appareil visé |
| `mid` | hex | message envoyé |
| `bytes` | entier | taille envoyée |
| `try` | entier ≥ 1 | rang de la tentative dans la couche (1 = premier membre essayé) |
| `ok` | booléen | issue (O4 : en simulation, le destinataire est en ligne) |
| `ctx` | `"route"`, `"esquad"` | saut d'une route, ou retransmission interne à l'e-squad |

**`relay_recv`** : écrit par le nœud qui reçoit un message de route.

| Champ | Type | Sens |
|---|---|---|
| `mid` | hex | message reçu |
| `bytes` | entier | taille reçue (sert à mesurer la fuite de position, D5) |
| `tries` | entier | déchiffrements asymétriques essayés sur l'enveloppe (coût, E2) |
| `result` | `"forward"`, `"deliver"`, `"reject"` | à relayer ; charge utile pour la dernière couche ; échec du déchiffrement (⊥) |
| `out` | hex ou `null` | message réémis, si `forward` |
| `next` | liste d'entiers ou `null` | membres de la couche suivante lus dans @, si `forward` |

**`drop`** : `mid` (message abandonné), `tried` (nombre de membres essayés). Un nœud qui l'écrit a échoué sur toute la couche suivante.

### 4.5 Transfert

| `ev` | Écrit par | Champs |
|---|---|---|
| `transfer_start` | émetteur | `did`, `chunks`, `window`, `rto_ms`, `dead_ms` |
| `chunk_sent` | émetteur | `did`, `idx`, `attempt` (1 = premier envoi, > 1 = renvoi), `mid`, `header_bytes` (en-tête oignon ajouté à la charge utile) |
| `chunk_recv` | récepteur | `did`, `idx`, `valid` (haché conforme à δ), `dup` (déjà reçu) |
| `ack_sent` | récepteur | `did`, `idx`, `mid`, `header_bytes` |
| `ack_recv` | émetteur | `did`, `idx`, `dup` (déjà acquitté) |
| `transfer_end` | les deux | `did`, `side` (`"sender"`, `"receiver"`), `outcome`, `chunks_done` |

`outcome` vaut :

- `"complete"` : côté émetteur, tous les chunks sont acquittés ; côté récepteur, le fichier est complet et vérifié. **Un fichier est compté transmis si et seulement si le récepteur écrit `transfer_end` `complete`** (D3).
- `"dead"` : côté émetteur seulement, aucun ACK pendant `dead_ms` (D3).
- `"aborted"` : abandon demandé par l'utilisateur.

Si la route aller meurt, le récepteur n'écrit rien : l'absence de `transfer_end` récepteur vaut « non transmis ».

## 5. Ce que chaque mesure utilise

| Mesure | Événements |
|---|---|
| E1 : transferts achevés, temps de complétion | `transfer_start`, `transfer_end` |
| E1 : succès par message, renvois par chunk | chaîne `chunk_sent` → `hop` / `relay_recv` → `esquad_rx`, `drop` ; `chunk_sent.attempt` |
| E2 : taille des couches, arrêts par L_max | `layer_built.members`, `layer_built.stop` |
| E2 : taille d'en-tête, coût de déchiffrement | `chunk_sent.header_bytes`, `ack_sent.header_bytes`, `relay_recv.tries` |
| E3 : composition des routes, adversaires | `layer_built`, `device.user` |
| E3 : messages saisis, exposition source / destinataire | chaîne par `mid` : qui a reçu quel message de qui |
| E3 : fuite de position (D5) | `relay_recv.bytes` rapproché du rang, connu par la chaîne |
| E4 : score des p(d) publiés, repli | `descriptor_published` et `churn` du tour suivant |
| E4 : calibration des couches | `layer_built.unavail` et `churn` des membres |
| E5 : Δ et route praticable au premier usage | `channel_offer.t`, `transfer_start.t`, `layer_built`, `churn` |
| E5 : couche fautive (RPS ou e-squad) | `drop`, et `layer_built.pos` de la couche visée |
| Cache borné, doublons, chunks corrompus (#29) | `cache.entries`, `esquad_rx.reason` |
| Convergence du gossip (O8) | `interaction`, `interaction_learned` |
| Visualisation (#38) | tous |

## 6. Relire une trace

Installation, une fois (environnement virtuel `.venv/` à la racine du dépôt, ignoré par git ; sous Debian ou Ubuntu, `pip` refuse d'installer dans le Python du système) :

```sh
sudo apt install python3-venv      # Debian / Ubuntu / WSL, si `python3 -m venv` échoue
python3 -m venv .venv
.venv/bin/pip install -r evaluation/requirements.txt
```

Puis, après `source .venv/bin/activate` :

```sh
python3 evaluation/traces.py evaluation/exemples/trace-exemple.jsonl
python3 -m unittest discover -s evaluation
```

La commande valide la trace, puis affiche un résumé calculé avec pandas. Elle sort en erreur si la trace ne respecte pas le format. La validation vérifie le schéma de chaque ligne, les bornes `run_start` / `run_end`, l'ordre des `t`, la déclaration de tout appareil cité, et deux invariants de simulation : un saut réussi vise un appareil en ligne d'après `churn`, et toute réception suit un saut réussi portant le même `mid`.

Depuis Python :

```python
from traces import split
tb = split("trace.jsonl")        # un DataFrame par type d'événement
tb["layer_built"].groupby("pos")["members"].apply(lambda m: m.str.len().mean())
```

La trace d'exemple raconte un transfert de 2 chunks entre 5 utilisateurs de 3 appareils. On y trouve un saut raté (relais éteint), une remise interne dans l'e-squad, un chunk mis en cache pendant l'absence de Bob, un renvoi abandonné parce que toute la couche FL3 est éteinte, puis la remise depuis le cache au retour de Bob. Les tailles d'en-tête y sont des ordres de grandeur, pas des mesures.
