use serde::{Deserialize, Serialize};

use crate::routing::Layer;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Route {
    layers: Vec<Layer>,
}

impl Route {
    pub fn new(layers: Vec<Layer>) -> Self {
        Self { layers }
    }

    pub fn layers(&self) -> &[Layer] {
        &self.layers
    }

    pub fn len(&self) -> usize {
        self.layers.len()
    }

    pub fn is_empty(&self) -> bool {
        self.layers.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HalfRoute(pub Route);

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{node::fixtures::node, test_utils::cbor_roundtrip};

    #[test]
    fn half_route_cbor_roundtrip() {
        let layers = (0..3)
            .map(|i| Layer::new(vec![node(2 * i), node(2 * i + 1)], 20).unwrap())
            .collect();
        let half = HalfRoute(Route::new(layers));
        assert_eq!(cbor_roundtrip(&half), half);
    }
}
