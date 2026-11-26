# Format des traces (v1)

Une trace décrit une exécution, simulée ou réelle, événement par événement. Ce document donne la liste des événements, leurs champs et la façon de relire une trace.

Fichiers associés :

- [evaluation/traces.py](../evaluation/traces.py) : schéma, chargement avec pandas, validation ;
- [evaluation/examples/example_trace.jsonl](../evaluation/examples/example_trace.jsonl) : trace d'exemple qui contient chaque type d'événement au moins une fois.

## 1. Principes

- **Un fichier par exécution** : `trace.jsonl`, ou `trace.jsonl.gz`. Une ligne = un objet JSON = un événement, en UTF-8, sans ligne vide.
- **Ordre** : les lignes sont écrites dans l'ordre d'exécution, donc `time_ms` ne décroît jamais. À `time_ms` égal, l'ordre des lignes est l'ordre d'exécution. En réseau réel, avec un fichier par processus, on fusionne les fichiers par un tri stable sur `time_ms`.
- **Bornes** : la première ligne est `run_started`, la dernière `run_ended`. Une trace sans `run_ended` est une exécution interrompue.
- **Déterminisme** : même graine, même trace, octet pour octet. Aucune valeur ne dépend du temps réel ni de l'ordre d'itération d'une table de hachage : un coût est noté en nombre d'opérations, jamais en durée.
- **Séparation** : `run_started`, `device_declared`, `availability_changed` et `run_ended` sont écrits par le banc d'essai (`crates/testbed`) et par lui seul. Les crates du protocole écrivent tous les autres événements. Aucun crate du protocole ne lit une trace.
- **Aucun contenu sensible** : ni clé, ni clair, ni données de chunk. Les messages sont désignés par une empreinte (`message_id`, §3).
- **Version** : `run_started.version` vaut 1. Ajouter un champ facultatif ne change pas la version. Renommer ou retirer un champ, ou en changer le sens, l'incrémente ; ce document, `evaluation/traces.py` et la trace d'exemple sont alors mis à jour ensemble.

## 2. Champs communs

| Champ | Type | Sens |
|---|---|---|
| `time_ms` | entier ≥ 0 | temps virtuel, en millisecondes depuis le début de l'exécution |
| `node` | entier, ou `null` | appareil qui écrit l'événement ; `null` seulement pour `run_started` et `run_ended` |
| `event` | chaîne | type de l'événement (§4) |

En simulation, le temps virtuel avance par sauts : seuls la latence d'un saut réseau, l'expiration d'un délai et le passage au tour suivant le font progresser. Le traitement d'un message ne prend aucun temps virtuel, si bien que plusieurs événements partagent souvent le même `time_ms`.

Le tour i (`Round`) d'un événement vaut ⌊`time_ms` / `params.round_duration_ms`⌋.

## 3. Conventions de valeurs

| Valeur | Représentation |
|---|---|
| Appareil (`node`, `target`, `members`…) | entier attribué par le banc d'essai, de 0 à N − 1 ; `device_declared` donne son `NodeId` |
| `file` | `FileId` : SHA-256 du fichier, en 64 caractères hexadécimaux minuscules ; identifie le fichier et son canal |
| `index` | `ChunkIndex` : rang du chunk, à partir de 0 |
| `message_id` | empreinte d'un message tel qu'il passe sur un lien : les 16 premiers caractères hexadécimaux du SHA-256 des octets envoyés |
| `direction` | `"forward"` : route aller (Alice → Bob, chunks) ; `"backward"` : route retour (Bob → Alice, ACK) |
| `position` | rang de la couche dans la route, de 1 à 4 ; 4 est l'e-squad du destinataire |
| Durées, tailles | millisecondes (suffixe `_ms`), octets (suffixe `_bytes`) |
| Probabilités | flottants dans [0, 1] |

**Suivre un message.** Un relais note le `message_id` du message reçu et celui du message qu'il réémet (`relay_received.message_id` → `relay_received.forwarded_message_id`), et chaque saut porte le `message_id` des octets envoyés. On chaîne donc `chunk_sent` → `hop_attempted` → `relay_received` → `hop_attempted` → … → `esquad_received`. Un même message essayé sur plusieurs membres d'une couche garde son `message_id`. Un renvoi est rechiffré : il a un `message_id` différent.

## 4. Événements

| `event` | Écrit par | Rôle |
|---|---|---|
| `run_started` | banc | paramètres de l'exécution |
| `device_declared` | banc | déclaration d'un appareil et de son utilisateur |
| `availability_changed` | banc | changement de disponibilité réelle d'un appareil |
| `run_ended` | banc | fin normale de l'exécution |
| `interaction_recorded` | e-squad | interaction ajoutée à la séquence de l'appareil, émise par lui ou reçue par gossip |
| `descriptor_published` | prédiction | descripteur publié dans le RPS avec p(d) |
| `channel_offered` | routes | message hors bande n° 1 produit (Alice) |
| `channel_accepted` | routes | message hors bande n° 2 produit (Bob) |
| `layer_built` | routes | couche construite (PickLayer, ou e-squad) |
| `route_completed` | routes | route complète à 4 couches |
| `hop_attempted` | relais | tentative d'envoi vers un nœud, et son issue |
| `relay_received` | relais | message reçu et déchiffré par un nœud |
| `message_dropped` | relais | abandon : tous les membres de la couche suivante ont échoué |
| `esquad_received` | e-squad | chunk ou ACK reçu en dernière couche, et ce qu'en fait l'appareil |
| `cache_updated` | e-squad | opération sur le cache de l'e-squad |
| `transfer_started` | transfert | premier usage du canal par l'émetteur |
| `chunk_sent` | transfert | chunk émis ou renvoyé |
| `chunk_received` | transfert | chunk reçu et vérifié contre δ par l'appareil récepteur |
| `ack_sent` | transfert | ACK émis |
| `ack_received` | transfert | ACK reçu par l'émetteur |
| `transfer_ended` | transfert | fin du transfert, côté émetteur ou récepteur |

Tous les champs listés ci-dessous sont obligatoires. Ceux qui peuvent être `null` le disent.

### 4.1 Banc d'essai

**`run_started`** (`node` = `null`)

| Champ | Type | Sens |
|---|---|---|
| `version` | entier | version du format (1) |
| `seed` | entier | graine de l'exécution |
| `params` | objet | paramètres de l'exécution ; seul `round_duration_ms` (durée d'un tour) est obligatoire |

Clés usuelles de `params` : `label`, `round_duration_ms`, `user_count`, `devices_per_user`, `churn_model`, `mean_availability`, `epsilon`, `max_layer_size`, `view_size`, `file_size`, `chunk_size`, `window_size`, `retransmit_timeout_ms`, `dead_channel_timeout_ms`, `hop_timeout_ms`, `usage_delay_ms` (délai entre la création du canal et son premier usage). D'autres clés peuvent s'ajouter.

**`device_declared`** : `user` (entier), l'utilisateur, donc l'e-squad, auquel appartient l'appareil ; `node_id` (64 caractères hexadécimaux), son `NodeId`. Un `device_declared` par appareil, avant tout autre événement qui le cite.

**`availability_changed`** : `online` (booléen). Un événement par appareil au temps 0 (état initial), puis un à chaque changement. L'état d'un appareil au tour i est son état au début de ce tour.

**`run_ended`** (`node` = `null`) : aucun champ.

### 4.2 E-squad et prédiction

**`interaction_recorded`** : écrit chaque fois qu'une interaction entre dans la séquence d'interactions de l'appareil `node`, qu'il l'ait émise lui-même ou reçue d'un autre membre de son e-squad par gossip. Toujours écrit.

| Champ | Type | Sens |
|---|---|---|
| `at` | entier | tour où l'interaction a eu lieu sur `actor` (`Round`) |
| `actor` | entier | appareil sur lequel l'interaction a eu lieu |
| `kind` | `"Use"`, `"Upload"`, `"Download"` | variante d'`InteractionKind` |
| `file` | `FileId` ou `null` | fichier porté par `Upload` et `Download` (`InteractionKind::file()`) ; `null` pour `Use` |
| `gossiper` | entier ou `null` | membre de l'e-squad qui a transmis l'interaction à `node` ; `null` si `node` l'a émise lui-même (`actor` = `node`) |

`at`, `actor`, `kind` et `file` identifient une interaction : toutes les lignes qui portent les mêmes valeurs décrivent la même interaction, émise une fois par `actor` puis apprise par chacun des autres membres. Le délai d'apprentissage est l'écart entre leurs `time_ms`. Le `gossiper` peut être un autre appareil que l'`actor` quand l'interaction a transité par un membre intermédiaire.

`Upload` et `Download` sont émis à la création du canal.

**`descriptor_published`**

| Champ | Type | Sens |
|---|---|---|
| `published_at` | entier | tour i de la prédiction |
| `availability` | flottant | P_i(d) publié |
| `used_fallback` | booléen | vrai si l'état courant n'avait jamais été vu et que le prédicteur a utilisé son repli |

**`esquad_received`** : écrit par un appareil de l'e-squad qui reçoit un chunk ou un ACK, soit en dernière couche d'une route, soit d'un autre membre de son e-squad.

| Champ | Type | Sens |
|---|---|---|
| `file`, `transfer_kind`, `index` | `FileId`, `"chunk"`/`"ack"`, entier | chunk ou ACK concerné |
| `message_id` | hex | message par lequel il est arrivé |
| `received_via` | `"route"`, `"esquad"` | dernière couche d'une route, ou retransmission interne |
| `action` | `"local"`, `"forward"`, `"cache"`, `"drop"` | remis au transfert de cet appareil ; transmis à l'appareil visé ; gardé ; jeté |
| `reason` | chaîne ou `null` | pour `cache` : `"offline"`, `"unknown_file"` ; pour `drop` : `"duplicate"`, `"bad_hash"`, `"unknown_file"` ; `null` sinon |

**`cache_updated`** : `file`, `transfer_kind`, `index`, `operation` (`"put"`, `"deliver"`, `"evict"`, `"expire"`), `entry_count` (nombre d'entrées du cache après l'opération). Un `esquad_received` d'action `cache` est suivi d'un `cache_updated` `put`. Un `deliver` est suivi du `hop_attempted` interne vers l'appareil visé.

### 4.3 Canaux et routes

**`channel_offered`** (Alice) : `file`, `size` (taille du fichier), `chunk_size`, `chunk_count`, `out_of_band_bytes` (taille codée du message hors bande n° 1).

**`channel_accepted`** (Bob) : `file`, `out_of_band_bytes` (taille du message n° 2).

**`layer_built`** : écrit par l'appareil qui construit la couche. Alice écrit BL3, BL4, FL1 et FL2 ; Bob écrit FL3, FL4, BL1 et BL2.

| Champ | Type | Sens |
|---|---|---|
| `file`, `direction`, `position` | | couche concernée |
| `members` | liste d'entiers | membres, dans l'ordre de la couche |
| `availability` | liste de flottants ou `null` | p(d) utilisés, dans le même ordre (`null` si inconnu) |
| `predicted_unavailability` | flottant ou `null` | indisponibilité prédite ∏(1 − p) |
| `stop_reason` | `"epsilon_reached"`, `"max_size_reached"`, `"view_exhausted"`, `"esquad_layer"` | arrêt de PickLayer : ε atteint, taille maximale atteinte, vue épuisée ; `"esquad_layer"` pour la couche 4, qui n'est pas tirée |
| `view_size` | entier ou `null` | nombre de candidats dans la vue au moment du tirage ; `null` pour la couche 4 |

**`route_completed`** : `file`, `direction`, `layer_sizes` (taille des 4 couches). Alice l'écrit pour `forward`, Bob pour `backward`.

### 4.4 Relayage

**`hop_attempted`** : une tentative d'envoi, écrite par l'expéditeur du saut (source, relais ou membre d'e-squad).

| Champ | Type | Sens |
|---|---|---|
| `target` | entier | appareil visé |
| `message_id` | hex | message envoyé |
| `size_bytes` | entier | taille envoyée |
| `rank_in_layer` | entier ≥ 1 | rang de la tentative dans la couche (1 = premier membre essayé) |
| `success` | booléen | issue de l'envoi ; en simulation, vrai si et seulement si l'appareil visé est en ligne |
| `context` | `"route"`, `"esquad"` | saut d'une route, ou retransmission interne à l'e-squad |

**`relay_received`** : écrit par le nœud qui reçoit un message de route.

| Champ | Type | Sens |
|---|---|---|
| `message_id` | hex | message reçu |
| `size_bytes` | entier | taille reçue |
| `decryption_attempts` | entier | déchiffrements asymétriques essayés sur l'enveloppe |
| `decision` | `"forward"`, `"deliver"`, `"reject"` | à relayer ; charge utile pour la dernière couche ; échec du déchiffrement (⊥) |
| `forwarded_message_id` | hex ou `null` | message réémis, si `forward` |
| `next_layer` | liste d'entiers ou `null` | membres de la couche suivante lus dans l'en-tête, si `forward` |

**`message_dropped`** : `message_id` (message abandonné), `attempted_targets` (nombre de membres essayés). Le nœud qui l'écrit a échoué sur toute la couche suivante.

### 4.5 Transfert

| `event` | Écrit par | Champs |
|---|---|---|
| `transfer_started` | émetteur | `file`, `chunk_count`, `window_size`, `retransmit_timeout_ms`, `dead_channel_timeout_ms` |
| `chunk_sent` | émetteur | `file`, `index`, `attempt` (1 = premier envoi, > 1 = renvoi), `message_id`, `header_bytes` (en-tête oignon ajouté à la charge utile) |
| `chunk_received` | récepteur | `file`, `index`, `hash_valid` (haché conforme à δ), `duplicate` (déjà reçu) |
| `ack_sent` | récepteur | `file`, `index`, `message_id`, `header_bytes` |
| `ack_received` | émetteur | `file`, `index`, `duplicate` (déjà acquitté) |
| `transfer_ended` | les deux | `file`, `side` (`"sender"`, `"receiver"`), `outcome`, `completed_chunks` |

`outcome` vaut :

- `"complete"` : côté émetteur, tous les chunks sont acquittés ; côté récepteur, le fichier est complet et vérifié. Un fichier est transmis si et seulement si le récepteur écrit `transfer_ended` avec `complete`.
- `"dead"` : côté émetteur seulement, aucun ACK reçu pendant `dead_channel_timeout_ms`.
- `"aborted"` : abandon demandé par l'utilisateur.

Si la route aller meurt, le récepteur n'écrit rien : sans `transfer_ended` côté récepteur, le fichier n'est pas transmis.

## 5. Relire une trace

Installation, une fois, dans un environnement virtuel `.venv/` à la racine du dépôt (sous Debian ou Ubuntu, `pip` refuse d'installer dans le Python du système) :

```sh
sudo apt install python3-venv      # Debian / Ubuntu / WSL, si `python3 -m venv` échoue
python3 -m venv .venv
.venv/bin/pip install -r evaluation/requirements.txt
```

Puis, après `source .venv/bin/activate` :

```sh
python3 evaluation/traces.py evaluation/examples/example_trace.jsonl
python3 -m unittest discover -s evaluation
```

La première commande valide la trace, puis affiche un résumé calculé avec pandas ; elle sort en erreur si la trace ne respecte pas le format. La validation vérifie :

- le schéma de chaque ligne ;
- la première ligne `run_started` et la dernière `run_ended` ;
- que `time_ms` ne décroît jamais ;
- que tout appareil cité a été déclaré par `device_declared` ;
- que l'`actor` et le `gossiper` d'une interaction sont dans l'e-squad de `node` ;
- qu'un saut réussi vise un appareil en ligne d'après `availability_changed` ;
- que toute réception suit un saut réussi portant le même `message_id`.

Depuis Python :

```python
from traces import split
tables = split("trace.jsonl")      # un DataFrame par type d'événement
tables["layer_built"].groupby("position")["members"].apply(lambda m: m.str.len().mean())
```

La trace d'exemple décrit un transfert de 2 chunks entre 5 utilisateurs de 3 appareils. On y trouve un saut raté (relais éteint), une remise interne dans l'e-squad, un chunk mis en cache pendant l'absence de Bob, un renvoi abandonné parce que toute la couche FL3 est éteinte, puis la remise depuis le cache au retour de Bob. Les tailles d'en-tête y sont des ordres de grandeur, pas des mesures.
