use serde::{Deserialize, Serialize};

use crate::transfer::{ChunkIndex, FileId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Ack {
    file: FileId,
    index: ChunkIndex,
}

impl Ack {
    pub fn new(file: FileId, index: ChunkIndex) -> Self {
        Self { file, index }
    }

    pub fn file(&self) -> FileId {
        self.file
    }

    pub fn index(&self) -> ChunkIndex {
        self.index
    }
}
