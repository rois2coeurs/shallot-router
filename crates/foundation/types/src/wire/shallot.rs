use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvelopeEntry {
    encapsulated_key: [u8; 32],
    #[serde(with = "crate::transfer::bytes")]
    wrapped_key: Vec<u8>,
}

impl EnvelopeEntry {
    pub fn new(encapsulated_key: [u8; 32], wrapped_key: Vec<u8>) -> Self {
        Self {
            encapsulated_key,
            wrapped_key,
        }
    }

    pub fn encapsulated_key(&self) -> &[u8; 32] {
        &self.encapsulated_key
    }

    pub fn wrapped_key(&self) -> &[u8] {
        &self.wrapped_key
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct Envelope(pub Vec<EnvelopeEntry>);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Ciphertext(#[serde(with = "crate::transfer::bytes")] pub Vec<u8>);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShallotMessage {
    envelope: Envelope,
    payload: Ciphertext,
}

impl ShallotMessage {
    pub fn new(envelope: Envelope, payload: Ciphertext) -> Self {
        Self { envelope, payload }
    }

    pub fn envelope(&self) -> &Envelope {
        &self.envelope
    }

    pub fn payload(&self) -> &Ciphertext {
        &self.payload
    }

    pub fn into_parts(self) -> (Envelope, Ciphertext) {
        (self.envelope, self.payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::cbor_roundtrip;
    use proptest::prelude::*;

    fn entry() -> impl Strategy<Value = EnvelopeEntry> {
        (
            any::<[u8; 32]>(),
            proptest::collection::vec(any::<u8>(), 48),
        )
            .prop_map(|(k, w)| EnvelopeEntry::new(k, w))
    }

    proptest! {
        #[test]
        fn shallot_cbor_roundtrip(
            entries in proptest::collection::vec(entry(), 0..20),
            payload in proptest::collection::vec(any::<u8>(), 0..1024),
        ) {
            let m = ShallotMessage::new(Envelope(entries), Ciphertext(payload));
            prop_assert_eq!(cbor_roundtrip(&m), m);
        }
    }
}
