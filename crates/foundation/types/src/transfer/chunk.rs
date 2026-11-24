use serde::{Deserialize, Serialize};

use crate::transfer::FileId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct ChunkIndex(pub u64);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Chunk {
    file: FileId,
    index: ChunkIndex,
    #[serde(with = "crate::transfer::bytes")]
    data: Vec<u8>,
}

impl Chunk {
    pub fn new(file: FileId, index: ChunkIndex, data: Vec<u8>) -> Self {
        Self { file, index, data }
    }

    pub fn file(&self) -> FileId {
        self.file
    }

    pub fn index(&self) -> ChunkIndex {
        self.index
    }

    pub fn data(&self) -> &[u8] {
        &self.data
    }

    pub fn into_data(self) -> Vec<u8> {
        self.data
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::cbor_roundtrip;
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn chunk_cbor_roundtrip(idx: u64, data in proptest::collection::vec(any::<u8>(), 0..2048)) {
            let c = Chunk::new(FileId::random(), ChunkIndex(idx), data);
            prop_assert_eq!(cbor_roundtrip(&c), c);
        }
    }

    #[test]
    fn data_is_encoded_as_byte_string() {
        let c = Chunk::new(FileId::random(), ChunkIndex(0), vec![0xFF; 100]);
        let mut buf = Vec::new();
        ciborium::into_writer(&c, &mut buf).unwrap();
        assert!(buf.len() < 200, "encodé en {} octets", buf.len());
    }
}
