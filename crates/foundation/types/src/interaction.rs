use serde::{Deserialize, Serialize};

use crate::{node::NodeId, time::Round, transfer::FileId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum InteractionKind {
    Use,
    Upload,
    Download,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Interaction {
    at: Round,
    actor: NodeId,
    kind: InteractionKind,
    file: FileId,
}

impl Interaction {
    pub fn new(at: Round, actor: NodeId, kind: InteractionKind, file: FileId) -> Self {
        Self {
            at,
            actor,
            kind,
            file,
        }
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

    pub fn file(&self) -> FileId {
        self.file
    }
}
