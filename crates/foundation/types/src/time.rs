use std::ops::{Add, AddAssign, Sub, SubAssign};

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

impl Add<u64> for Round {
    type Output = Round;

    fn add(self, rounds: u64) -> Round {
        Round(self.0 + rounds)
    }
}

impl AddAssign<u64> for Round {
    fn add_assign(&mut self, rounds: u64) {
        self.0 += rounds;
    }
}

impl Sub<u64> for Round {
    type Output = Round;

    fn sub(self, rounds: u64) -> Round {
        Round(self.0 - rounds)
    }
}

impl SubAssign<u64> for Round {
    fn sub_assign(&mut self, rounds: u64) {
        self.0 -= rounds;
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

    #[test]
    fn add_rounds() {
        assert_eq!(Round(5) + 3, Round(8));
        let mut r = Round(2);
        r += 4;
        assert_eq!(r, Round(6));
    }

    #[test]
    fn sub_rounds() {
        assert_eq!(Round(8) - 3, Round(5));
        let mut r = Round(6);
        r -= 4;
        assert_eq!(r, Round(2));
    }
}
