pub mod crypto;
pub mod error;
pub mod interaction;
pub mod node;
pub mod routing;
pub mod time;
pub mod transfer;
pub mod wire;

pub use crypto::{Digest, PublicKey};
pub use error::TypesError;
pub use interaction::{Interaction, InteractionKind};
pub use node::{NodeAddr, NodeDescriptor, NodeId, NodeInfo, Probability};
pub use routing::{HalfRoute, Layer, Route};
pub use time::Round;
pub use transfer::{Ack, Chunk, ChunkIndex, FileDescriptor, FileId};
pub use wire::{Ciphertext, Envelope, EnvelopeEntry, ShallotMessage};

#[cfg(test)]
pub(crate) mod test_utils {
    use serde::{Serialize, de::DeserializeOwned};

    pub fn cbor_roundtrip<T: Serialize + DeserializeOwned>(value: &T) -> T {
        let mut buf = Vec::new();
        ciborium::into_writer(value, &mut buf).expect("encode");
        ciborium::from_reader(buf.as_slice()).expect("decode")
    }
}
