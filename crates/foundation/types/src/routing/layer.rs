use serde::{Deserialize, Serialize};

use crate::{error::TypesError, node::NodeInfo};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Layer {
    members: Vec<NodeInfo>,
}

impl Layer {
    pub fn new(members: Vec<NodeInfo>, l_max: usize) -> Result<Self, TypesError> {
        if members.is_empty() {
            return Err(TypesError::EmptyLayer);
        }
        if members.len() > l_max {
            return Err(TypesError::LayerTooLarge {
                len: members.len(),
                max: l_max,
            });
        }
        Ok(Self { members })
    }

    pub fn members(&self) -> &[NodeInfo] {
        &self.members
    }

    pub fn len(&self) -> usize {
        self.members.len()
    }

    pub fn is_empty(&self) -> bool {
        self.members.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node::fixtures::node;

    #[test]
    fn enforces_bounds() {
        let members: Vec<_> = (0..3).map(node).collect();
        assert!(Layer::new(members.clone(), 3).is_ok());
        assert_eq!(
            Layer::new(members, 2),
            Err(TypesError::LayerTooLarge { len: 3, max: 2 })
        );
        assert_eq!(Layer::new(vec![], 20), Err(TypesError::EmptyLayer));
    }
}
