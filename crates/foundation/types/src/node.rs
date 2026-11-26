mod descriptor;

pub use descriptor::{NodeDescriptor, Probability};

use std::net::SocketAddr;

use serde::{Deserialize, Serialize};

use crate::crypto::{Digest, PublicKey};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct NodeId(pub Digest);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeAddr(pub SocketAddr);

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeInfo {
    id: NodeId,
    public_key: PublicKey,
    addr: NodeAddr,
}

impl NodeInfo {
    pub fn new(id: NodeId, public_key: PublicKey, addr: NodeAddr) -> Self {
        Self {
            id,
            public_key,
            addr,
        }
    }

    pub fn id(&self) -> NodeId {
        self.id
    }

    pub fn public_key(&self) -> &PublicKey {
        &self.public_key
    }

    pub fn addr(&self) -> NodeAddr {
        self.addr
    }
}

#[cfg(test)]
pub(crate) mod fixtures {
    use super::*;

    pub fn node(n: u8) -> NodeInfo {
        NodeInfo::new(
            NodeId(Digest([n; 32])),
            PublicKey([n.wrapping_add(1); 32]),
            NodeAddr(SocketAddr::from(([127, 0, 0, 1], 4000 + u16::from(n)))),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::fixtures::node;
    use crate::test_utils::cbor_roundtrip;

    #[test]
    fn node_info_cbor_roundtrip() {
        let n = node(7);
        assert_eq!(cbor_roundtrip(&n), n);
    }
}
