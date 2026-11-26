use std::collections::VecDeque;

use shallot_types::{Interaction, InteractionKind, NodeId, Round};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AvailabilityMatrix {
    devices: Vec<NodeId>,
    columns: VecDeque<Vec<bool>>,
    start: Round,
    capacity: usize,
}

impl AvailabilityMatrix {
    pub fn new(devices: Vec<NodeId>, start: Round, capacity: usize) -> Self {
        assert!(capacity > 0, "AvailabilityMatrix: capacity must be > 0");
        Self {
            devices,
            columns: VecDeque::with_capacity(capacity),
            start,
            capacity,
        }
    }
    pub fn from_interactions(
        devices: Vec<NodeId>,
        interactions: &[Interaction],
        start: Round,
        end: Round,
    ) -> Self {
        let span = usize::try_from(end.since(start)).expect("range too large");
        let mut matrix = Self::new(devices, start, span.max(1));
        matrix.advance_to(end);
        for interaction in interactions.iter().filter(|i| i.at() < end) {
            matrix.record(interaction);
        }
        matrix
    }

    pub fn record(&mut self, interaction: &Interaction) {
        if !matches!(interaction.kind(), InteractionKind::Use) {
            return;
        }
        let Some(k) = self.index_of(interaction.actor()) else {
            return;
        };
        let at = interaction.at();
        if at < self.start {
            return;
        }
        if at >= self.end() {
            self.advance_to(at.next());
        }
        let j = self.offset(at);
        self.columns[j][k] = true;
    }

    pub fn advance_to(&mut self, now: Round) {
        let gap = now.since(self.end());
        if gap == 0 {
            return;
        }
        let capacity = self.capacity as u64;
        if gap >= capacity {
            self.columns.clear();
            self.start = now - capacity;
            self.push_zero_columns(self.capacity);
            return;
        }
        let gap = gap as usize;
        let overflow = (self.columns.len() + gap).saturating_sub(self.capacity);
        self.columns.drain(..overflow);
        self.start += overflow as u64;
        self.push_zero_columns(gap);
    }

    pub fn column(&self, round: Round) -> Option<&[bool]> {
        if round < self.start {
            return None;
        }
        self.columns
            .get(usize::try_from(round.since(self.start)).ok()?)
            .map(Vec::as_slice)
    }

    pub fn columns(&self) -> impl ExactSizeIterator<Item = &[bool]> + DoubleEndedIterator {
        self.columns.iter().map(Vec::as_slice)
    }

    pub fn get(&self, device: NodeId, round: Round) -> Option<bool> {
        let k = self.index_of(device)?;
        self.column(round).map(|column| column[k])
    }

    pub fn devices(&self) -> &[NodeId] {
        &self.devices
    }

    pub fn start(&self) -> Round {
        self.start
    }

    /// Exclusive end of the window: the next round to be added.
    pub fn end(&self) -> Round {
        self.start + self.columns.len() as u64
    }

    pub fn capacity(&self) -> usize {
        self.capacity
    }

    pub fn len(&self) -> usize {
        self.columns.len()
    }

    pub fn is_empty(&self) -> bool {
        self.columns.is_empty()
    }

    fn index_of(&self, device: NodeId) -> Option<usize> {
        self.devices.iter().position(|d| *d == device)
    }

    fn offset(&self, round: Round) -> usize {
        round.since(self.start) as usize
    }

    fn push_zero_columns(&mut self, count: usize) {
        let rows = self.devices.len();
        self.columns
            .extend(std::iter::repeat_with(|| vec![false; rows]).take(count));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use shallot_types::{Digest, FileId};

    fn dev(n: u8) -> NodeId {
        NodeId(Digest([n; 32]))
    }

    fn use_at(n: u8, round: u64) -> Interaction {
        Interaction::new(Round(round), dev(n), InteractionKind::Use)
    }

    fn squad() -> Vec<NodeId> {
        vec![dev(1), dev(2), dev(3)]
    }

    fn row(m: &AvailabilityMatrix, n: u8) -> Vec<bool> {
        (m.start().0..m.end().0)
            .map(|r| m.get(dev(n), Round(r)).unwrap())
            .collect()
    }

    #[test]
    fn hand_written_sequence() {
        let uses = [
            use_at(1, 0),
            use_at(1, 1),
            use_at(1, 2),
            use_at(2, 1),
            use_at(2, 3),
            use_at(1, 4),
            use_at(2, 4),
        ];
        let m = AvailabilityMatrix::from_interactions(squad(), &uses, Round(0), Round(5));

        assert_eq!(m.len(), 5);
        assert_eq!(row(&m, 1), [true, true, true, false, true]);
        assert_eq!(row(&m, 2), [false, true, false, true, true]);
        assert_eq!(row(&m, 3), [false; 5]);
        assert_eq!(m.column(Round(1)), Some(&[true, true, false][..]));
        assert_eq!(m.column(Round(3)), Some(&[false, true, false][..]));
    }

    #[test]
    fn window_boundaries() {
        let uses = [use_at(1, 9), use_at(1, 10), use_at(2, 13), use_at(3, 14)];
        let m = AvailabilityMatrix::from_interactions(squad(), &uses, Round(10), Round(14));

        assert_eq!((m.start(), m.end(), m.len()), (Round(10), Round(14), 4));
        assert_eq!(m.get(dev(1), Round(10)), Some(true), "start is included");
        assert_eq!(
            m.get(dev(2), Round(13)),
            Some(true),
            "last turn is included"
        );
        assert_eq!(m.get(dev(3), Round(14)), None, "end is excluded");
        assert_eq!(m.get(dev(1), Round(9)), None, "before start is excluded");
        assert_eq!(row(&m, 3), [false; 4]);
    }

    #[test]
    fn incremental_matches_one_shot() {
        let uses = [use_at(1, 0), use_at(3, 1), use_at(2, 2), use_at(1, 3)];
        let expected = AvailabilityMatrix::from_interactions(squad(), &uses, Round(0), Round(4));

        let mut m = AvailabilityMatrix::new(squad(), Round(0), 4);
        for u in &uses {
            m.record(u);
        }
        m.advance_to(Round(4));
        assert_eq!(m, expected);
    }

    #[test]
    fn late_use_updates_existing_column() {
        let mut m = AvailabilityMatrix::new(squad(), Round(0), 10);
        m.advance_to(Round(5));
        assert_eq!(m.get(dev(2), Round(2)), Some(false));

        m.record(&use_at(2, 2));
        assert_eq!(m.get(dev(2), Round(2)), Some(true));
        assert_eq!(m.len(), 5);
    }

    #[test]
    fn record_beyond_end_fills_gap_with_zeros() {
        let mut m = AvailabilityMatrix::new(squad(), Round(0), 10);
        m.record(&use_at(1, 0));
        m.record(&use_at(1, 4));

        assert_eq!(m.end(), Round(5));
        assert_eq!(row(&m, 1), [true, false, false, false, true]);
    }

    #[test]
    fn sliding_window_drops_oldest() {
        let mut m = AvailabilityMatrix::new(squad(), Round(0), 3);
        m.record(&use_at(1, 1));
        m.advance_to(Round(5));

        assert_eq!((m.start(), m.end(), m.len()), (Round(2), Round(5), 3));
        assert_eq!(m.get(dev(1), Round(1)), None);

        m.record(&use_at(1, 1));
        assert_eq!(
            row(&m, 1),
            [false; 3],
            "a USE older than the window is ignored"
        );
    }

    #[test]
    fn long_gap_is_bounded() {
        let mut m = AvailabilityMatrix::new(squad(), Round(0), 3);
        m.record(&use_at(1, 0));
        m.advance_to(Round(1_000_000));

        assert_eq!(
            (m.start(), m.end(), m.len()),
            (Round(999_997), Round(1_000_000), 3)
        );
        assert!(m.columns().all(|c| c == [false; 3]));
    }

    #[test]
    fn duplicates_other_kinds_and_strangers() {
        let file = FileId(Digest([9; 32]));
        let interactions = [
            use_at(1, 0),
            use_at(1, 0),
            Interaction::new(Round(1), dev(2), InteractionKind::Upload(file)),
            Interaction::new(Round(1), dev(3), InteractionKind::Download(file)),
            use_at(42, 1),
        ];
        let m = AvailabilityMatrix::from_interactions(squad(), &interactions, Round(0), Round(2));

        assert_eq!(m.column(Round(0)), Some(&[true, false, false][..]));
        assert_eq!(m.column(Round(1)), Some(&[false, false, false][..]));
        assert_eq!(m.get(dev(42), Round(1)), None);
    }

    #[test]
    fn empty_range() {
        let uses = [use_at(1, 3)];
        let m = AvailabilityMatrix::from_interactions(squad(), &uses, Round(3), Round(3));
        assert!(m.is_empty());
        assert_eq!(m.end(), Round(3));

        let m = AvailabilityMatrix::from_interactions(squad(), &uses, Round(5), Round(2));
        assert!(m.is_empty());
    }

    #[test]
    fn advance_backwards_is_noop() {
        let mut m = AvailabilityMatrix::new(squad(), Round(0), 5);
        m.advance_to(Round(3));
        m.advance_to(Round(1));
        assert_eq!(m.end(), Round(3));
    }
}
