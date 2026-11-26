use serde::{Deserialize, Serialize};

use crate::crypto::Digest;

/// Hash SHA-256 of file
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct FileId(pub Digest);

impl FileId {
    pub fn digest(&self) -> &Digest {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FileDescriptor {
    id: FileId,
    size: u64,
    chunk_count: u64,
}

impl FileDescriptor {
    pub fn new(id: FileId, size: u64, chunk_count: u64) -> Self {
        Self {
            id,
            size,
            chunk_count,
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::cbor_roundtrip;

    #[test]
    fn descriptor_cbor_roundtrip() {
        let d = FileDescriptor::new(FileId(Digest([9; 32])), 10_000, 10);
        assert_eq!(cbor_roundtrip(&d), d);
    }
}
