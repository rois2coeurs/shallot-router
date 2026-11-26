use serde::{Deserialize, Serialize};

use crate::{error::TypesError, node::NodeInfo, time::Round};

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(try_from = "f64", into = "f64")]
pub struct Probability(f64);

impl Probability {
    pub fn new(p: f64) -> Result<Self, TypesError> {
        if (0.0..=1.0).contains(&p) {
            Ok(Self(p))
        } else {
            Err(TypesError::InvalidProbability(p))
        }
    }

    pub fn get(self) -> f64 {
        self.0
    }
}

impl TryFrom<f64> for Probability {
    type Error = TypesError;

    fn try_from(p: f64) -> Result<Self, Self::Error> {
        Self::new(p)
    }
}

impl From<Probability> for f64 {
    fn from(p: Probability) -> f64 {
        p.0
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NodeDescriptor {
    node: NodeInfo,
    availability: Probability,
    published_at: Round,
}

impl NodeDescriptor {
    pub fn new(node: NodeInfo, availability: Probability, published_at: Round) -> Self {
        Self {
            node,
            availability,
            published_at,
        }
    }

    pub fn node(&self) -> &NodeInfo {
        &self.node
    }

    pub fn availability(&self) -> Probability {
        self.availability
    }

    pub fn published_at(&self) -> Round {
        self.published_at
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{node::fixtures::node, test_utils::cbor_roundtrip};
    use proptest::prelude::*;

    #[test]
    fn probability_rejects_out_of_range_and_nan() {
        assert!(Probability::new(0.0).is_ok());
        assert!(Probability::new(1.0).is_ok());
        assert!(Probability::new(-0.1).is_err());
        assert!(Probability::new(1.1).is_err());
        assert!(Probability::new(f64::NAN).is_err());
        assert!(Probability::new(f64::INFINITY).is_err());
    }

    #[test]
    fn probability_deserialization_is_validated() {
        let mut buf = Vec::new();
        ciborium::into_writer(&2.0_f64, &mut buf).unwrap();
        assert!(ciborium::from_reader::<Probability, _>(buf.as_slice()).is_err());
    }

    proptest! {
        #[test]
        fn descriptor_cbor_roundtrip(n: u8, p in 0.0f64..=1.0, r: u64) {
            let d = NodeDescriptor::new(node(n), Probability::new(p).unwrap(), Round(r));
            prop_assert_eq!(cbor_roundtrip(&d), d);
        }
    }
}
