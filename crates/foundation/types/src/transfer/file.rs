use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::crypto::Digest;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct FileId(pub Uuid);

impl FileId {
    pub fn random() -> Self {
        Self(Uuid::new_v4())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FileDescriptor {
    id: FileId,
    size: u64,
    chunk_count: u64,
    digest: Digest,
}

impl FileDescriptor {
    pub fn new(id: FileId, size: u64, chunk_count: u64, digest: Digest) -> Self {
        Self {
            id,
            size,
            chunk_count,
            digest,
        }
    }

    pub fn id(&self) -> FileId {
        self.id
    }

    pub fn size(&self) -> u64 {
        self.size
    }

    pub fn chunk_count(&self) -> u64 {
        self.chunk_count
    }

    pub fn digest(&self) -> &Digest {
        &self.digest
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::cbor_roundtrip;

    #[test]
    fn descriptor_cbor_roundtrip() {
        let d = FileDescriptor::new(FileId::random(), 10_000, 10, Digest([9; 32]));
        assert_eq!(cbor_roundtrip(&d), d);
    }
}
