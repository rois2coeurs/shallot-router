use serde::{Deserialize, Serialize};

/// Clé publique X25519 (32 octets).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct PublicKey(pub [u8; 32]);

/// Empreinte SHA-256 (32 octets).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Digest(pub [u8; 32]);

impl PublicKey {
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }
}

impl Digest {
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }
}
