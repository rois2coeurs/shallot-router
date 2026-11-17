# Décisions d'équipe

Registre des décisions techniques du projet. Une décision n'est rediscutée que par une nouvelle entrée datée qui la remplace explicitement.

ε dans nos documents correspond au θ de SPORES.

---

## Séance du 12 novembre 2026 (J0, issue #2)

Règle de séance : on ne débat que les lignes contestées ; une ligne non contestée est adoptée telle que proposée.

### Choix techniques T1 à T12

| Choix | Statut | Décision | Raison |
|---|---|---|---|
| T1 Codage | Adoptée | CBOR via `serde` et `ciborium` | Auto-descriptif, relisible depuis Python |
| T2 Primitives | **Corrigée** | **HPKE** (RFC 9180, suite DHKEM(X25519, HKDF-SHA256) / HKDF-SHA256 / ChaCha20-Poly1305), **ChaCha20-Poly1305** pour le chiffré symétrique, **SHA-256** pour le hachage. `crypto_box`, AES-256-GCM et BLAKE3 sont écartés | Environ 80 octets par membre d'enveloppe (32 de clé encapsulée + 32 de clé + 16 de tag) contre 256 en RSA 2048 ; l'AEAD détecte l'échec (⊥) comme l'exige l'Alg. 1 ; HPKE est normalisé, un seul choix évite les variantes |
| T3 Bibliothèque | Adoptée | RustCrypto (crates `hpke`, `chacha20poly1305`, `sha2`, `x25519-dalek`) | Rust pur, aucune dépendance C |
| T4 Simulation | Adoptée | Moteur à événements discrets maison, un seul processus | Naturel avec un cœur sans entrées-sorties |
| T5 Exécution | Adoptée | Cœur sans entrées-sorties (machines à états), adaptateur `tokio` pour le réel | Pas de code asynchrone dans le protocole |
| T6 Transport réel | Adoptée | TCP | Suffisant pour un démonstrateur local |
| T7 Hors bande | Adoptée | Fichier ou bloc de texte à copier | Une demi-route pèse environ 10 Kio, trop pour un code QR |
| T8 Persistance | **Corrigée** | Fichiers sérialisés avec `serde`, **écrits dans un fichier temporaire puis renommés** sur le fichier cible (renommage atomique), pour qu'un arrêt brutal ne corrompe rien | Palier X seulement |
| T9 Démonstrateur | Adoptée | Visualisation web qui rejoue les traces de simulation ; transfert réel au palier X | Indépendant du réseau réel |
| T10 Tests | Adoptée | `proptest` ; `cargo-fuzz` sur les décodeurs | Les relais lisent des octets venant d'inconnus |
| T11 Analyse | Adoptée | Python (pandas, matplotlib) | Figures rapides à produire |
| T12 Traces | Adoptée | Lignes JSON | Lisibles, chargeables avec pandas |

### Points ouverts tranchés

| Point | Statut | Décision |
|---|---|---|
| O1 Protocole indépendant du socle | Adoptée | Oui : cœur sans entrées-sorties, socle simulé d'abord, socle `tokio` au palier X |
| O3 Recouvrements entre couches | **Corrigée** | Exclure d'une couche : les nœuds déjà présents dans la route, ses propres appareils **et les appareils de l'e-squad du correspondant** (l_V = 60 le permet). L'option fidèle à SPORES (ne rien exclure) reste une variante de E3 |
| O4 Sens de « envoi réussi » | Adoptée | En simulation : le destinataire est en ligne. En réel : acquittement applicatif du nœud suivant après réception complète |
| O7 Paramètres du Selective Repeat | Adoptée | Fenêtre de 10 chunks, minuteur fixe de 10 s, configurables, calibrés au J3 sur l'aller-retour mesuré |
| O9 Paramètres du RPS simulé | Adoptée | Vue renouvelée à chaque tour, descripteur périmé après 3 tours sans republication, propres appareils exclus |

O3, O4, O7 et O9 sont nos propositions : SPORES ne donne pas ces valeurs.

### Report des corrections dans les issues

| Correction | Issues concernées | Modification à reporter |
|---|---|---|
| T2 | #6 [T1.1] Chiffrement broadcast hybride | Remplacer « X25519 hybride, ChaCha20-Poly1305 ou AES-256-GCM » par « HPKE (X25519, HKDF-SHA256, ChaCha20-Poly1305) » |
| T2 | #17 [T3.1] Descripteur δ | Remplacer « BLAKE3 ou SHA-256 » par « SHA-256 » |
| T8 | #41 [T6.2] Persistance | Ajouter : écriture dans un fichier temporaire puis renommage ; attendu « un arrêt brutal pendant l'écriture ne corrompt pas l'état » |
| O3 | #14 [T2.3] PickLayer | Ajouter l'exclusion des appareils de l'e-squad du correspondant |

---

## Décisions du 10 novembre 2026 (rappel, non rediscutées)

| # | Décision |
|---|---|
| D1 | Prédicteur de Markov à un tour de SPORES, p(d) publié tel quel, PickLayer inchangé ; l'effet du délai est mesuré (E4, E5) |
| D3 | Un canal = un fichier ; canal mort si l'émetteur ne reçoit aucun ACK pendant une durée D (au moins 20 tours) ; pas de reprise |
| D4 | Comme SPORES : extrémités soumises au churn, dernière couche = e-squad qui fait suivre ou met en cache, ACK émis par l'appareil récepteur, minuteur fixe |
| D5 | Pas de bourrage ; la fuite de position est mesurée et documentée |
| D6 | Taille de couche bornée par L_max = 20 (configurable) |
| D7 | Robustesse au mensonge sur p(d) : hors périmètre |
| D8 | La disponibilité réelle n'est jamais lue par le protocole, seulement exportée vers les traces |
| D9 | RPS simulé à vue partielle aléatoire, l_V = 60 par défaut |
| D10 | SHA-1 écartée au profit d'un hachage récent (SHA-256, cf. T2) |
| D11 | Canal lié à l'appareil créateur, δ partagé dans l'e-squad |
| D13 | Interactions UL et DL émises à la création du canal |
