use serde::{Deserialize, Serialize};

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default, Serialize, Deserialize,
)]
pub struct Round(pub u64);

impl Round {
    pub const ZERO: Round = Round(0);

    pub fn next(self) -> Round {
        Round(self.0 + 1)
    }

    pub fn since(self, earlier: Round) -> u64 {
        self.0.saturating_sub(earlier.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn since_saturates() {
        assert_eq!(Round(5).since(Round(2)), 3);
        assert_eq!(Round(2).since(Round(5)), 0);
        assert_eq!(Round::ZERO.next(), Round(1));
    }
}
