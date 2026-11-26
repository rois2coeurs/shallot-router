use serde::{Deserialize, Serialize};

use crate::{node::NodeId, time::Round, transfer::FileId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum InteractionKind {
    Use,
    Upload(FileId),
    Download(FileId),
}

impl InteractionKind {
    pub fn file(&self) -> Option<FileId> {
        match self {
            Self::Use => None,
            Self::Upload(file) | Self::Download(file) => Some(*file),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Interaction {
    at: Round,
    actor: NodeId,
    kind: InteractionKind,
}

impl Interaction {
    pub fn new(at: Round, actor: NodeId, kind: InteractionKind) -> Self {
        Self { at, actor, kind }
    }

    pub fn at(&self) -> Round {
        self.at
    }

    pub fn actor(&self) -> NodeId {
        self.actor
    }

    pub fn kind(&self) -> InteractionKind {
        self.kind
    }

    pub fn file(&self) -> Option<FileId> {
        self.kind.file()
    }
}
